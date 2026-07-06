# Q: what is editable mode?
# A: https://setuptools.pypa.io/en/latest/userguide/development_mode.html
{
  inputs ?
    (
      let
        flake-compatish = import (
          fetchTree (builtins.fromJSON (builtins.readFile ./flake.lock)).nodes.flake-compatish.locked
        );
      in
      flake-compatish {
        source = ./.;
        # Use nixpkgs from NIX_PATH if configured
        overrides =
          let
            nixpkgs = builtins.tryEval <nixpkgs>;
          in
          if nixpkgs.success then
            builtins.warn "using nixpkgs from NIX_PATH" {
              nixpkgs = nixpkgs.value;
            }
          else
            builtins.warn "using nixpkgs from flake.lock" { };
      }
    ).inputs,
  pkgs ? import inputs.nixpkgs (import ./nix/pkgsSettings.nix { }),
}:
rec {
  # (re)export nixpkgs
  inherit pkgs;
  inherit (pkgs) lib;
  inherit inputs;
  # instantiate uv2nix and friends
  pyproject-nix = import inputs.pyproject-nix { inherit lib; };
  uv2nix = import inputs.uv2nix { inherit pyproject-nix lib; };
  pyproject-build-systems = import inputs.pyproject-build-systems {
    inherit pyproject-nix uv2nix lib;
  };
  # import mkApplication helper
  inherit (pkgs.callPackage pyproject-nix.build.util { }) mkApplication;
  # load uv workspace
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
  # find a compatible Python interpreter
  python = lib.head (
    pyproject-nix.lib.util.filterPythonInterpreters {
      inherit (workspace) requires-python;
      inherit (pkgs) pythonInterpreters;
    }
  );
  # instantiate pyproject-nix builders
  pythonBase = pkgs.callPackage pyproject-nix.build.packages {
    inherit python;
  };
  # overlay packages from uv.lock
  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel"; # sdist | wheel
  };
  # overlay packages from uv.lock in editable mode
  editableOverlay = workspace.mkEditablePyprojectOverlay {
    root = "$REPO_ROOT";
  };
  # Python package set
  pythonSet = pythonBase.overrideScope (
    lib.composeManyExtensions [
      pyproject-build-systems.overlays.wheel
      overlay
      (final: prev: {
        # overlay hatchling to depend on editables for the devshell
        hatchling = prev.hatchling.overrideAttrs (old: {
          passthru = old.passthru // {
            dependencies = old.passthru.dependencies // {
              editables = [ ];
            };
          };
        });
      })
    ]
  );
  # Editable Python package set
  editablePythonSet = pythonSet.overrideScope editableOverlay;
  # venv
  venv = pythonSet.mkVirtualEnv "weav-dev-env" workspace.deps.all;
  # editable venv
  editableVenv = editablePythonSet.mkVirtualEnv "weav-editable-dev-env" workspace.deps.all;
  # development shell allowing 0 effort Python development
  shell = pkgs.callPackage ./nix/shell.nix {
    inherit pythonSet editableVenv;
  };
  # weav runnable package
  weav = mkApplication {
    venv = pythonSet.mkVirtualEnv "weav-env" workspace.deps.default;
    package = pythonSet.weav;
  };
}
