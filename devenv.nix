{
  config,
  inputs,
  lib,
  pkgs,
  ...
}: {
  overlays = [inputs.js-toolchain-overlay.overlays.default];

  languages = {
    python = {
      enable = true;
      package = pkgs.python314;
      directory = "./backend";

      venv.enable = true;

      uv = {
        enable = true;
        sync.enable = true;
      };

      lsp = {
        enable = true;
        package = pkgs.ty;
      };
    };

    javascript = {
      enable = true;
      package = pkgs.node-bin.lts;
      nodejs.enable = true;
      pnpm = {
        enable = true;
        package = lib.defaultTo pkgs.pnpm-bin.latest (pkgs.pnpm-bin.fromProject ./.);
      };
      lsp.enable = true;
    };
    typescript = {
      enable = true;
      lsp.enable = true;
    };
  };

  scripts.pnpm-up.exec = let
    major = lib.versions.major config.languages.javascript.pnpm.package.version;
    latestInMajor = pkgs.pnpm-bin.majors.${major};
  in ''
    pnpm pkg set packageManager=pnpm@${latestInMajor.version}
    # The wrapper's pm-on-fail=ignore skips recording the pin in pnpm-lock.yaml; running the pinned version avoids pnpm downloading itself
    ${lib.getExe latestInMajor} install --lockfile-only --pm-on-fail=download
  '';

  enterTest = ''
    python --version
    uv --version
    node --version
    pnpm --version
    command -v ty
  '';
}
