{
  description = "CodeGraph";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit system;};
    in {
      devShells.default = pkgs.mkShell {
        packages = [
          pkgs.python312
          pkgs.uv
        ];

        env = {
          UV_PYTHON_DOWNLOADS = "never";
          UV_PYTHON = pkgs.python312.interpreter;
        };

        shellHook = ''
          unset PYTHONPATH
          # export UV_PROJECT_ENVIRONMENT="$(pwd)/.venv"
        '';
      };
    });
}
