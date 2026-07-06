{
  # nixpkgs
  lib,
  installShellFiles,
  # python build
  buildPythonApplication,
  hatchling,
  # deps
  rich,
  jinja2,
  ruamel-yaml,
  typer,
  platformdirs,
}:
buildPythonApplication (finalAttrs: {
  name = "phabfive";
  version = (fromTOML (builtins.readFile ../pyproject.toml)).project.version;
  src = lib.cleanSource ../.;
  pyproject = true;
  build-system = [ hatchling ];
  dependencies = [
    installShellFiles
    # deps
    rich
    jinja2
    ruamel-yaml
    typer
    platformdirs
  ];
  postInstall = # bash
    ''
      # Install shell completions into "well-known" folders (NixOS and home-manager will pick these up)
      installShellCompletion --name phabfive --bash <(env _PHABFIVE_COMPLETE=source_bash $out/bin/phabfive)
      installShellCompletion --name phabfive --fish <(env _PHABFIVE_COMPLETE=source_fish $out/bin/phabfive)
      installShellCompletion --name phabfive --zsh <(env _PHABFIVE_COMPLETE=source_zsh $out/bin/phabfive)
    '';
  meta = {
    homepage = "https://github.com/dynamist/weav";
    description = "Markup template compiler with data support";
    license = [ lib.licenses.asl20 ];
    mainProgram = "weav";
    maintainers = [ lib.maintainers.lillecarl ];
  };
})
