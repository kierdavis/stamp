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

    packages."x86_64-linux" = let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
        overlays = [ self.overlays.default ];
      };
    in { inherit (pkgs) stamp; };
  };
}
