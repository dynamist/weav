# this flake doens't look like a normal flake, we're using default.nix to allow
# users to import weav with their own nixpkgs instance and to enable evaluating
# without copying to the Nix store while maintaining full flake compatibility.
{
  inputs = {
    flake-compatish = {
      url = "github:lillecarl/flake-compatish";
      flake = false;
    };
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      flake = false;
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      flake = false;
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      flake = false;
    };
  };
  outputs =
    inputs:
    let
      lib = inputs.nixpkgs.lib;
      # attrSet generator generating sets for all supported systems (what NixOS Hydra builds and caches)
      eachSys = func: lib.genAttrs (lib.importJSON "${inputs.nixpkgs}/ci/supportedSystems.json") func;
      # instantiate nixpkgs for each supported system
      eachPkgs = eachSys (
        system: import inputs.nixpkgs (import ./nix/pkgsSettings.nix { inherit system; })
      );
      # import default.nix for each supported system
      eachDefNix = eachSys (
        system:
        import ./. {
          inherit (eachPkgs.${system}) pkgs;
          inherit inputs;
        }
      );
    in
    {
      # expose weav for each system
      packages = eachSys (
        system:
        let
          defNix = eachDefNix.${system};
        in
        rec {
          default = weav;
          inherit (defNix) weav;
        }
      );
      # expose devShell for each system
      devShells = eachSys (
        system:
        let
          defNix = eachDefNix.${system};
        in
        {
          default = defNix.shell;
        }
      );
      # re-export nixpkgs
      legacyPackages = eachSys (system: eachDefNix.${system}.shell);
    };
}
