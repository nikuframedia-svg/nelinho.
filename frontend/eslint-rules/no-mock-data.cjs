/**
 * ESLint Rule: no-mock-data
 * Part of TIER 4: CI/DEVOPS & FUTURE
 * 
 * "Zero Mock Enforcement"
 * Disallow mock data in production components to ensure
 * all displayed data comes from real API calls.
 */

module.exports = {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow mock data in production components',
      category: 'Best Practices',
      recommended: true,
    },
    fixable: null,
    schema: [
      {
        type: 'object',
        properties: {
          allowInTests: {
            type: 'boolean',
            default: true,
          },
          allowInStories: {
            type: 'boolean',
            default: true,
          },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      mockDataDetected: 'Mock data detected: "{{ pattern }}". Use API calls instead.',
      mockPatternDetected: 'Potential mock/placeholder data detected: "{{ value }}"',
      hardcodedArrayDetected: 'Large inline array detected with {{ count }} objects. Consider fetching from API.',
      mockImportDetected: 'Mock data import detected: "{{ source }}". Remove mock imports from production code.',
    },
  },
  
  create(context) {
    const options = context.options[0] || {};
    const allowInTests = options.allowInTests !== false;
    const allowInStories = options.allowInStories !== false;
    
    const filename = context.getFilename();
    
    // Skip test files if allowed
    if (allowInTests && (
      filename.includes('.test.') ||
      filename.includes('.spec.') ||
      filename.includes('__tests__') ||
      filename.includes('__mocks__')
    )) {
      return {};
    }
    
    // Skip story files if allowed
    if (allowInStories && (
      filename.includes('.stories.') ||
      filename.includes('.story.')
    )) {
      return {};
    }

    const FORBIDDEN_PATTERNS = [
      { pattern: /mockData/i, name: 'mockData' },
      { pattern: /MOCK_/i, name: 'MOCK_' },
      { pattern: /faker\./i, name: 'faker.' },
      { pattern: /dummyData/i, name: 'dummyData' },
      { pattern: /testData/i, name: 'testData' },
      { pattern: /sampleData/i, name: 'sampleData' },
    ];

    const FORBIDDEN_VALUES = [
      'lorem ipsum',
      'placeholder',
      'dummy',
      'sample data',
      'test data',
      'mock value',
      'foo',
      'bar',
      'baz',
    ];

    const FORBIDDEN_IMPORT_PATTERNS = [
      /mock/i,
      /fixtures/i,
      /stub/i,
    ];

    return {
      // Check variable declarations
      VariableDeclarator(node) {
        const sourceCode = context.getSourceCode();
        const text = sourceCode.getText(node);
        
        for (const { pattern, name } of FORBIDDEN_PATTERNS) {
          if (pattern.test(text)) {
            context.report({
              node,
              messageId: 'mockDataDetected',
              data: { pattern: name },
            });
            break;
          }
        }
      },

      // Check string literals
      Literal(node) {
        if (typeof node.value === 'string') {
          const lowerValue = node.value.toLowerCase();
          
          for (const forbidden of FORBIDDEN_VALUES) {
            if (lowerValue.includes(forbidden)) {
              context.report({
                node,
                messageId: 'mockPatternDetected',
                data: { value: node.value.substring(0, 50) },
              });
              break;
            }
          }
        }
      },

      // Check for large inline arrays that might be hardcoded data
      ArrayExpression(node) {
        // Only flag large arrays of objects (likely mock data)
        if (
          node.elements.length > 5 && 
          node.elements.every(el => el && el.type === 'ObjectExpression')
        ) {
          // Check if it's inside a constant that looks like data
          const parent = node.parent;
          if (parent && parent.type === 'VariableDeclarator') {
            const name = parent.id && parent.id.name;
            if (name && (
              name.toLowerCase().includes('data') ||
              name.toLowerCase().includes('items') ||
              name.toLowerCase().includes('list') ||
              name.toLowerCase().includes('array')
            )) {
              context.report({
                node,
                messageId: 'hardcodedArrayDetected',
                data: { count: node.elements.length },
              });
            }
          }
        }
      },

      // Check imports
      ImportDeclaration(node) {
        const source = node.source.value;
        
        for (const pattern of FORBIDDEN_IMPORT_PATTERNS) {
          if (pattern.test(source)) {
            // Skip if it's from node_modules (like @faker-js which might be dev only)
            if (!source.startsWith('.') && !source.startsWith('/')) {
              continue;
            }
            
            context.report({
              node,
              messageId: 'mockImportDetected',
              data: { source },
            });
            break;
          }
        }
      },

      // Check function calls
      CallExpression(node) {
        // Check for Math.random() which might indicate mock data generation
        if (
          node.callee.type === 'MemberExpression' &&
          node.callee.object.name === 'Math' &&
          node.callee.property.name === 'random'
        ) {
          // This is a warning, not an error - Math.random has legitimate uses
          // Could add an option to enable/disable this check
        }
      },
    };
  },
};

