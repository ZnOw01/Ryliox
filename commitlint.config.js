module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Tipo obligatorio en lowercase
    'type-case': [2, 'always', 'lower-case'],
    'type-empty': [2, 'never'],
    // Tipos permitidos
    'type-enum': [
      2,
      'always',
      [
        'feat',      // Nueva característica
        'fix',       // Corrección de bug
        'docs',      // Documentación
        'style',     // Cambios de estilo (formato, sin cambio de código)
        'refactor',  // Refactorización
        'perf',      // Mejora de performance
        'test',      // Tests
        'build',     // Build system o dependencias
        'ci',        // CI/CD
        'chore',     // Tareas de mantenimiento
        'revert',    // Revertir commit
        'security',  // Seguridad
        'dx',        // Developer experience
      ],
    ],
    // Scope opcional
    'scope-case': [2, 'always', 'lower-case'],
    'scope-empty': [0, 'never'], // Opcional
    // Subject
    'subject-case': [0, 'never'], // Permite cualquier case
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'subject-max-length': [2, 'always', 100],
    'subject-min-length': [2, 'always', 5],
    // Body
    'body-case': [0, 'never'],
    'body-leading-blank': [1, 'always'],
    'body-max-line-length': [2, 'always', 100],
    // Footer
    'footer-leading-blank': [1, 'always'],
    'footer-max-line-length': [2, 'always', 100],
    // Referencias a issues
    'references-empty': [0, 'never'],
  },
  helpUrl: 'https://github.com/conventional-changelog/commitlint/#what-is-commitlint',
  prompt: {
    messages: {
      skip: ':skip',
      max: 'maximum %d chars',
      min: 'minimum %d chars',
      emptyWarning: 'can not be empty',
      upperLimitWarning: 'over limit',
      lowerLimitWarning: 'below limit',
    },
    questions: {
      type: {
        description: "Select the type of change that you're committing:",
        enum: {
          feat: {
            description: 'A new feature',
            title: 'Features',
            emoji: '✨',
          },
          fix: {
            description: 'A bug fix',
            title: 'Bug Fixes',
            emoji: '🐛',
          },
          docs: {
            description: 'Documentation only changes',
            title: 'Documentation',
            emoji: '📚',
          },
          style: {
            description: 'Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)',
            title: 'Styles',
            emoji: '💎',
          },
          refactor: {
            description: 'A code change that neither fixes a bug nor adds a feature',
            title: 'Code Refactoring',
            emoji: '📦',
          },
          perf: {
            description: 'A code change that improves performance',
            title: 'Performance Improvements',
            emoji: '🚀',
          },
          test: {
            description: 'Adding missing tests or correcting existing tests',
            title: 'Tests',
            emoji: '🚨',
          },
          build: {
            description: 'Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)',
            title: 'Builds',
            emoji: '🛠',
          },
          ci: {
            description: 'Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)',
            title: 'Continuous Integrations',
            emoji: '⚙️',
          },
          chore: {
            description: "Other changes that don't modify src or test files",
            title: 'Chores',
            emoji: '♻️',
          },
          revert: {
            description: 'Reverts a previous commit',
            title: 'Reverts',
            emoji: '🗑',
          },
          security: {
            description: 'A code change that fixes a security issue',
            title: 'Security',
            emoji: '🔒',
          },
          dx: {
            description: 'Improvements to developer experience',
            title: 'Developer Experience',
            emoji: '🔧',
          },
        },
      },
      scope: {
        description: 'What is the scope of this change (e.g. component or file name)',
      },
      subject: {
        description: 'Write a short, imperative tense description of the change',
      },
      body: {
        description: 'Provide a longer description of the change',
      },
      isBreaking: {
        description: 'Are there any breaking changes?',
      },
      breakingBody: {
        description: 'A BREAKING CHANGE commit requires a body. Please enter a longer description of the commit itself',
      },
      breaking: {
        description: 'Describe the breaking changes',
      },
      isIssueAffected: {
        description: 'Does this change affect any open issues?',
      },
      issuesBody: {
        description: 'If issues are closed, the commit requires a body. Please enter a longer description of the commit itself',
      },
      issues: {
        description: 'Add issue references (e.g. "fix #123", "ref #456")',
      },
    },
  },
};
