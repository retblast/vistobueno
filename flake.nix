{
  description = "Validador de formato de tesis - entorno de desarrollo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        pythonEnv = pkgs.python314.withPackages (ps: with ps; [
          fastapi
          uvicorn
          pydantic
          pyyaml
          python-docx
          pymupdf
          pytesseract
          pillow
          lxml
          pytest
          httpx
          python-multipart
        ]);

        tesseractSpa = pkgs.tesseract.override {
          enableLanguages = [ "spa" "eng" ];
        };
      in
      {
        # Entorno de desarrollo
        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.ocrmypdf
            tesseractSpa
            pkgs.poppler-utils
          ];

          shellHook = ''
            echo "=== VistoBueno — entorno de desarrollo ==="
            echo "Python: $(python3 --version)"
            echo ""
            echo "Comandos disponibles:"
            echo "  nix run .#test -- tests/ -v                    # ejecutar tests"
            echo "  nix run .#serve -- validator.api:app --reload  # iniciar API"
            echo "  nix flake check                                # tests + verificación"
            echo "  python3 scripts/generate_openapi.py            # regenerar OpenAPI spec"
            echo "  python3 scripts/eval_contra_plantillas.py recursos/  # evaluar batch"
            echo ""
          '';
        };

        # Aplicaciones ejecutables con nix run
        apps = {
          default = self.apps.${system}.test;

          test = {
            type = "app";
            program = "${pythonEnv}/bin/pytest";
          };

          serve = {
            type = "app";
            program = "${pythonEnv}/bin/uvicorn";
          };
        };

        # Verificaciones: pytest via nix flake check
        checks = {
          default = pkgs.runCommand "vistobueno-tests" {
            buildInputs = [ pythonEnv ];
          } ''
            cp -r ${self}/* .
            pytest tests/ -v
            touch $out
          '';
        };
      });
}
