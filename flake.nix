{
  inputs = {
    nixpkgs = {
      type = "github";
      owner = "NixOS";
      repo = "nixpkgs";
      ref = "nixos-25.05";
    };
  };

  outputs = { self, nixpkgs, ... }: {
    overlays.default = import ./nix/overlay.nix;
  };
}
