// @ts-check
const config = {
  title: 'libgitledger',
  tagline: 'Git-native, append-only ledger core',
  description: 'Git-native, append-only ledger core in C. Documentation and developer resources.',
  url: 'https://flyingrobots.github.io',
  baseUrl: '/libgitledger/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  organizationName: 'flyingrobots',
  projectName: 'libgitledger',
  trailingSlash: false,
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        property: 'og:image',
        content: 'https://flyingrobots.github.io/libgitledger/img/og-image.png',
      },
    },
  ],
  markdown: { mermaid: true },
  themes: ['@docusaurus/theme-mermaid'],
  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */ ({
        docs: {
          path: '../docs',
          routeBasePath: '/docs',
          sidebarPath: require.resolve('./sidebars.js'),
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */ ({
      navbar: {
        title: 'libgitledger',
        hideOnScroll: false,
        items: [
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */ ({
      mermaid: {
        theme: { light: 'neutral', dark: 'dark' },
      },
      navbar: {
        title: 'libgitledger',
        items: [
          { to: '/docs', label: 'Docs', position: 'left' },
          { to: '/docs/ROADMAP-DAG', label: 'Roadmap', position: 'left' },
          { href: 'https://github.com/flyingrobots/libgitledger', label: 'GitHub', position: 'right' },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Project',
            items: [
              { label: 'Roadmap DAG', to: '/docs/ROADMAP-DAG' },
              { label: 'Issues Board', href: 'https://github.com/users/flyingrobots/projects/6' },
            ],
          },
          {
            title: 'Repo',
            items: [
              { label: 'GitHub', href: 'https://github.com/flyingrobots/libgitledger' },
            ],
          },
        ],
        copyright: `© ${new Date().getFullYear()} libgitledger`,
      },
    }),
};

module.exports = config;

