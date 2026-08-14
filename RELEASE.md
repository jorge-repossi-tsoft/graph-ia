# Release

Checklist corta para publicar `graph-ia` sin arrastrar artefactos locales.

1. Actualizar la versi?n en ambos manifests:
   `python3 scripts/bump-version.py 3.1.1`
2. Correr validaciones:
   `python3 -m unittest discover -s tests`
3. Generar el bundle limpio y el bundle versionado:
   `python3 scripts/build-release.py --versioned`
4. Verificar que exista el zip final:
   `dist/graph-ia-release-v3.1.1.zip`
5. Publicar usando ese zip y crear el tag sugerido:
   `v3.1.1`

Notas:
- `scripts/build-release.py` valida que `.claude-plugin/plugin.json` y `.codex-plugin/plugin.json` compartan la misma versi?n.
- El bundle excluye `.agents/`, `tests/`, `dist/`, caches y temporales locales.
- `dist/` es generado e ignorado por git; si quer?s rehacer un release, simplemente corr? el script de nuevo.
