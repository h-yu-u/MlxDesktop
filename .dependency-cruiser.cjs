module.exports = {
  forbidden: [
    {
      name: 'no-domain-to-ui-or-infrastructure',
      severity: 'error',
      from: { path: '/domain/' },
      to: { path: '(vue|pinia|naive-ui|fastapi|pydantic|tauri|mlx|sqlite)' },
    },
    {
      name: 'no-cross-feature-chat-imports',
      severity: 'warn',
      from: { path: '^apps/desktop/src/modules/([^/]+)/' },
      to: { path: '^apps/desktop/src/modules/(?!$1/)[^/]+/' },
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    tsConfig: { fileName: 'apps/desktop/tsconfig.app.json' },
    exclude: 'node_modules|dist|generated-schema',
  },
}
