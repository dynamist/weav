# reusable nixpkgs settings
{
  system ? builtins.currentSystem,
}:
{
  inherit system;
  config = {
    allowUnfree = true;
    overlays = [ ];
  };
}
