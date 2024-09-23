_default:
  @just --list
build:
  whiskers kicad.tera
  zip -r catppuccin-kicad.zip colors resources LICENSE metadata.json
