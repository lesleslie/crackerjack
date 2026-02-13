______________________________________________________________________

title: Accessibility Audit
owner: Platform Reliability Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXCRHAG8PDWTJ5W6WTXJR
  category: monitoring

______________________________________________________________________

## Accessibility Audit and Testing

You are an accessibility expert specializing in WCAG compliance, inclusive design, and assistive technology compatibility. Conduct comprehensive audits, identify barriers, provide remediation guidance, and ensure digital products are accessible to all users.

## Context

The user needs to audit and improve accessibility to ensure compliance with WCAG standards and provide an inclusive experience for users with disabilities. Focus on automated testing, manual verification, remediation strategies, and establishing ongoing accessibility practices.

## Requirements

$ARGUMENTS

## Instructions

### 1. Automated Accessibility Testing

Implement comprehensive automated testing:

**Accessibility Test Suite**

```javascript
// accessibility-test-suite.js
const { AxePuppeteer } = require('@axe-core/puppeteer');
const puppeteer = require('puppeteer');
const pa11y = require('pa11y');
const htmlValidator = require('html-validator');

class AccessibilityAuditor {
    constructor(options = {}) {
        this.wcagLevel = options.wcagLevel || 'AA';
        this.viewport = options.viewport || { width: 1920, height: 1080 };
        this.results = [];
    }
    
    async runFullAudit(url) {
        console.log(`🔍 Starting accessibility audit for ${url}`);
        
        const results = {
            url,
            timestamp: new Date().toISOString(),
            summary: {},
            violations: [],
            passes: [],
            incomplete: [],
            inapplicable: []
        };
        
        // Run multiple testing tools
        const [axeResults, pa11yResults, htmlResults] = await Promise.all([
            this.runAxeCore(url),
            this.runPa11y(url),
            this.validateHTML(url)
        ]);
        
        // Combine results
        results.violations = this.mergeViolations([
            ...axeResults.violations,
            ...pa11yResults.violations
        ]);
        
        results.htmlErrors = htmlResults.errors;
        results.summary = this.generateSummary(results);
        
        return results;
    }
    
    async runAxeCore(url) {
        const browser = await puppeteer.launch();
        const page = await browser.newPage();
        await page.setViewport(this.viewport);
        await page.goto(url, { waitUntil: 'networkidle2' });
        
        // Configure axe
        const axeBuilder = new AxePuppeteer(page)
            .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
            .disableRules(['color-contrast']) // Will test separately
            .exclude('.no-a11y-check');
        
        const results = await axeBuilder.analyze();
        await browser.close();
        
        return this.formatAxeResults(results);
    }
    
    async runPa11y(url) {
        const results = await pa11y(url, {
            standard: 'WCAG2AA',
            runners: ['axe', 'htmlcs'],
            includeWarnings: true,
            viewport: this.viewport,
            actions: [
                'wait for element .main-content to be visible'
            ]
        });
        
        return this.formatPa11yResults(results);
    }
    
    formatAxeResults(results) {
        return {
            violations: results.violations.map(violation => ({
                id: violation.id,
                impact: violation.impact,
                description: violation.description,
                help: violation.help,
                helpUrl: violation.helpUrl,
                nodes: violation.nodes.map(node => ({
                    html: node.html,
                    target: node.target,
                    failureSummary: node.failureSummary
                }))
            })),
            passes: results.passes.length,
            incomplete: results.incomplete.length
        };
    }
    
    generateSummary(results) {
        const violationsByImpact = {
            critical: 0,
            serious: 0,
            moderate: 0,
            minor: 0
        };
        
        results.violations.forEach(violation => {
            if (violationsByImpact.hasOwnProperty(violation.impact)) {
                violationsByImpact[violation.impact]++;
            }
        });
        
        return {
            totalViolations: results.violations.length,
            violationsByImpact,
            score: this.calculateAccessibilityScore(results),
            wcagCompliance: this.assessWCAGCompliance(results)
        };
    }
    
    calculateAccessibilityScore(results) {
        // Simple scoring algorithm
        const weights = {
            critical: 10,
            serious: 5,
            moderate: 2,
            minor: 1
        };
        
        let totalWeight = 0;
        results.violations.forEach(violation => {
            totalWeight += weights[violation.impact] || 0;
        });
        
        // Score from 0-100
        return Math.max(0, 100 - totalWeight);
    }
}

// Component-level testing
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

describe('Accessibility Tests', () => {
    it('should have no accessibility violations', async () => {
        const { container } = render(<MyComponent />);
        const results = await axe(container);
        expect(results).toHaveNoViolations();
    });
    
    it('should have proper ARIA labels', async () => {
        const { container } = render(<Form />);
        const results = await axe(container, {
            rules: {
                'label': { enabled: true },
                'aria-valid-attr': { enabled: true },
                'aria-roles': { enabled: true }
            }
        });
        expect(results).toHaveNoViolations();
    });
});
```

### 2. Color Contrast Analysis

Implement comprehensive color contrast testing:

**Color Contrast Checker**

```javascript
// color-contrast-analyzer.js
class ColorContrastAnalyzer {
    constructor() {
        this.wcagLevels = {
            'AA': { normal: 4.5, large: 3 },
            'AAA': { normal: 7, large: 4.5 }
        };
    }
    
    async analyzePageContrast(page) {
        const contrastIssues = [];
        
        // Extract all text elements with their styles
        const elements = await page.evaluate(() => {
            const allElements = document.querySelectorAll('*');
            const textElements = [];
            
            allElements.forEach(el => {
                if (el.innerText && el.innerText.trim()) {
                    const styles = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    
                    textElements.push({
                        text: el.innerText.trim(),
                        selector: el.tagName.toLowerCase() + 
                                 (el.id ? `#${el.id}` : '') +
                                 (el.className ? `.${el.className.split(' ').join('.')}` : ''),
                        color: styles.color,
                        backgroundColor: styles.backgroundColor,
                        fontSize: parseFloat(styles.fontSize),
                        fontWeight: styles.fontWeight,
                        position: { x: rect.x, y: rect.y },
                        isVisible: rect.width > 0 && rect.height > 0
                    });
                }
            });
            
            return textElements;
        });
        
        // Check contrast for each element
        for (const element of elements) {
            if (!element.isVisible) continue;
            
            const contrast = this.calculateContrast(
                element.color,
                element.backgroundColor
            );
            
            const isLargeText = this.isLargeText(
                element.fontSize,
                element.fontWeight
            );
            
            const requiredContrast = isLargeText ? 
                this.wcagLevels.AA.large : 
                this.wcagLevels.AA.normal;
            
            if (contrast < requiredContrast) {
                contrastIssues.push({
                    selector: element.selector,
                    text: element.text.substring(0, 50) + '...',
                    currentContrast: contrast.toFixed(2),
                    requiredContrast,
                    foreground: element.color,
                    background: element.backgroundColor,
                    recommendation: this.generateColorRecommendation(
                        element.color,
                        element.backgroundColor,
                        requiredContrast
                    )
                });
            }
        }
        
        return contrastIssues;
    }
    
    calculateContrast(foreground, background) {
        const rgb1 = this.parseColor(foreground);
        const rgb2 = this.parseColor(background);
        
        const l1 = this.relativeLuminance(rgb1);
        const l2 = this.relativeLuminance(rgb2);
        
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        
        return (lighter + 0.05) / (darker + 0.05);
    }
    
    relativeLuminance(rgb) {
        const [r, g, b] = rgb.map(val => {
            val = val / 255;
            return val <= 0.03928 ? 
                val / 12.92 : 
                Math.pow((val + 0.055) / 1.055, 2.4);
        });
        
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }
    
    generateColorRecommendation(foreground, background, targetRatio) {
        // Suggest adjusted colors that meet contrast requirements
        const suggestions = [];
        
        // Try darkening foreground
        const darkerFg = this.adjustColorForContrast(
            foreground,
            background,
            targetRatio,
            'darken'
        );
        if (darkerFg) {
            suggestions.push({
                type: 'darken-foreground',
                color: darkerFg,
                contrast: this.calculateContrast(darkerFg, background)
            });
        }
        
        // Try lightening background
        const lighterBg = this.adjustColorForContrast(
            background,
            foreground,
            targetRatio,
            'lighten'
        );
        if (lighterBg) {
            suggestions.push({
                type: 'lighten-background',
                color: lighterBg,
                contrast: this.calculateContrast(foreground, lighterBg)
            });
        }
        
        return suggestions;
    }
}

// CSS for high contrast mode
const highContrastStyles = `
@media (prefers-contrast: high) {
    :root {
        --text-primary: #000;
        --text-secondary: #333;
        --bg-primary: #fff;
        --bg-secondary: #f0f0f0;
        --border-color: #000;
    }
    
    * {
        border-color: var(--border-color) !important;
    }
    
    a {
        text-decoration: underline !important;
        text-decoration-thickness: 2px !important;
    }
    
    button, input, select, textarea {
        border: 2px solid var(--border-color) !important;
    }
}

@media (prefers-color-scheme: dark) and (prefers-contrast: high) {
    :root {
        --text-primary: #fff;
        --text-secondary: #ccc;
        --bg-primary: #000;
        --bg-secondary: #1a1a1a;
        --border-color: #fff;
    }
}
`;
```

### 3. Keyboard Navigation Testing

Test keyboard accessibility:

**Keyboard Navigation Tester**

```javascript
// keyboard-navigation-test.js
class KeyboardNavigationTester {
    async testKeyboardNavigation(page) {
        const results = {
            focusableElements: [],
            tabOrder: [],
            keyboardTraps: [],
            missingFocusIndicators: [],
            inaccessibleInteractive: []
        };
        
        // Get all focusable elements
        const focusableElements = await page.evaluate(() => {
            const selector = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
            const elements = document.querySelectorAll(selector);
            
            return Array.from(elements).map((el, index) => ({
                tagName: el.tagName.toLowerCase(),
                type: el.type || null,
                text: el.innerText || el.value || el.placeholder || '',
                tabIndex: el.tabIndex,
                hasAriaLabel: !!el.getAttribute('aria-label'),
                hasAriaLabelledBy: !!el.getAttribute('aria-labelledby'),
                selector: el.tagName.toLowerCase() + 
                         (el.id ? `#${el.id}` : '') +
                         (el.className ? `.${el.className.split(' ').join('.')}` : '')
            }));
        });
        
        results.focusableElements = focusableElements;
        
        // Test tab order
        for (let i = 0; i < focusableElements.length; i++) {
            await page.keyboard.press('Tab');
            
            const focusedElement = await page.evaluate(() => {
                const el = document.activeElement;
                return {
                    tagName: el.tagName.toLowerCase(),
                    selector: el.tagName.toLowerCase() + 
                             (el.id ? `#${el.id}` : '') +
                             (el.className ? `.${el.className.split(' ').join('.')}` : ''),
                    hasFocusIndicator: window.getComputedStyle(el).outline !== 'none'
                };
            });
            
            results.tabOrder.push(focusedElement);
            
            if (!focusedElement.hasFocusIndicator) {
                results.missingFocusIndicators.push(focusedElement);
            }
        }
        
        // Test for keyboard traps
        await this.detectKeyboardTraps(page, results);
        
        // Test interactive elements
        await this.testInteractiveElements(page, results);
        
        return results;
    }
    
    async detectKeyboardTraps(page, results) {
        // Test common trap patterns
        const trapSelectors = [
            'div[role="dialog"]',
            '.modal',
            '.dropdown-menu',
            '[role="menu"]'
        ];
        
        for (const selector of trapSelectors) {
            const elements = await page.$$(selector);
            
            for (const element of elements) {
                const canEscape = await this.testEscapeability(page, element);
                if (!canEscape) {
                    results.keyboardTraps.push({
                        selector,
                        issue: 'Cannot escape with keyboard'
                    });
                }
            }
        }
    }
    
    async testInteractiveElements(page, results) {
        // Find elements with click handlers but no keyboard support
        const clickableElements = await page.evaluate(() => {
            const elements = document.querySelectorAll('*');
            const clickable = [];
            
            elements.forEach(el => {
                const hasClickHandler = 
                    el.onclick || 
                    el.getAttribute('onclick') ||
                    (window.getEventListeners && 
                     window.getEventListeners(el).click);
                
                const isNotNativelyClickable = 
                    !['a', 'button', 'input', 'select', 'textarea'].includes(
                        el.tagName.toLowerCase()
                    );
                
                if (hasClickHandler && isNotNativelyClickable) {
                    const hasKeyboardSupport = 
                        el.getAttribute('tabindex') !== null ||
                        el.getAttribute('role') === 'button' ||
                        el.onkeydown || 
                        el.onkeyup;
                    
                    if (!hasKeyboardSupport) {
                        clickable.push({
                            selector: el.tagName.toLowerCase() + 
                                     (el.id ? `#${el.id}` : ''),
                            issue: 'Click handler without keyboard support'
                        });
                    }
                }
            });
            
            return clickable;
        });
        
        results.inaccessibleInteractive = clickableElements;
    }
}

// Keyboard navigation enhancement
function enhanceKeyboardNavigation() {
    // Skip to main content link
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Skip to main content';
    document.body.insertBefore(skipLink, document.body.firstChild);
    
    // Add keyboard event handlers
    document.addEventListener('keydown', (e) => {
        // Escape key closes modals
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal.open');
            if (modal) {
                closeModal(modal);
            }
        }
        
        // Arrow key navigation for menus
        if (e.key.startsWith('Arrow')) {
            const menu = document.activeElement.closest('[role="menu"]');
            if (menu) {
                navigateMenu(menu, e.key);
                e.preventDefault();
            }
        }
    });
    
    // Ensure all interactive elements are keyboard accessible
    document.querySelectorAll('[onclick]').forEach(el => {
        if (!el.hasAttribute('tabindex') && 
            !['a', 'button', 'input'].includes(el.tagName.toLowerCase())) {
            el.setAttribute('tabindex', '0');
            el.setAttribute('role', 'button');
            
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    el.click();
                    e.preventDefault();
                }
            });
        }
    });
}
```

### 4. Screen Reader Testing

Implement screen reader compatibility testing:

**Screen Reader Test Suite**

```javascript
// screen-reader-test.js
class ScreenReaderTester {
    async testScreenReaderCompatibility(page) {
        const results = {
            landmarks: await this.testLandmarks(page),
            headings: await this.testHeadingStructure(page),
            images: await this.testImageAccessibility(page),
            forms: await this.testFormAccessibility(page),
            tables: await this.testTableAccessibility(page),
            liveRegions: await this.testLiveRegions(page),
            semantics: await this.testSemanticHTML(page)
        };
        
        return results;
    }
    
    async testLandmarks(page) {
        const landmarks = await page.evaluate(() => {
            const landmarkRoles = [
                'banner', 'navigation', 'main', 'complementary', 
                'contentinfo', 'search', 'form', 'region'
            ];
            
            const found = [];
            
            // Check ARIA landmarks
            landmarkRoles.forEach(role => {
                const elements = document.querySelectorAll(`[role="${role}"]`);
                elements.forEach(el => {
                    found.push({
                        type: role,
                        hasLabel: !!(el.getAttribute('aria-label') || 
                                   el.getAttribute('aria-labelledby')),
                        selector: this.getSelector(el)
                    });
                });
            });
            
            // Check HTML5 landmarks
            const html5Landmarks = {
                'header': 'banner',
                'nav': 'navigation',
                'main': 'main',
                'aside': 'complementary',
                'footer': 'contentinfo'
            };
            
            Object.entries(html5Landmarks).forEach(([tag, role]) => {
                const elements = document.querySelectorAll(tag);
                elements.forEach(el => {
                    if (!el.closest('[role]')) {
                        found.push({
                            type: role,
                            hasLabel: !!(el.getAttribute('aria-label') || 
                                       el.getAttribute('aria-labelledby')),
                            selector: tag
                        });
                    }
                });
            });
            
            return found;
        });
        
        return {
            landmarks,
            issues: this.analyzeLandmarkIssues(landmarks)
        };
    }
    
    async testHeadingStructure(page) {
        const headings = await page.evaluate(() => {
            const allHeadings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
            const structure = [];
            
            allHeadings.forEach(heading => {
                structure.push({
                    level: parseInt(heading.tagName[1]),
                    text: heading.textContent.trim(),
                    hasAriaLevel: !!heading.getAttribute('aria-level'),
                    isEmpty: !heading.textContent.trim()
                });
            });
            
            return structure;
        });
        
        // Analyze heading structure
        const issues = [];
        let previousLevel = 0;
        
        headings.forEach((heading, index) => {
            // Check for skipped levels
            if (heading.level > previousLevel + 1 && previousLevel !== 0) {
                issues.push({
                    type: 'skipped-level',
                    message: `Heading level ${heading.level} skips from level ${previousLevel}`,
                    heading: heading.text
                });
            }
            
            // Check for empty headings
            if (heading.isEmpty) {
                issues.push({
                    type: 'empty-heading',
                    message: `Empty h${heading.level} element`,
                    index
                });
            }
            
            previousLevel = heading.level;
        });
        
        // Check for missing h1
        if (!headings.some(h => h.level === 1)) {
            issues.push({
                type: 'missing-h1',
                message: 'Page is missing an h1 element'
            });
        }
        
        return { headings, issues };
    }
    
    async testFormAccessibility(page) {
        const forms = await page.evaluate(() => {
            const formElements = document.querySelectorAll('form');
            const results = [];
            
            formElements.forEach(form => {
                const inputs = form.querySelectorAll('input, textarea, select');
                const formData = {
                    hasFieldset: !!form.querySelector('fieldset'),
                    hasLegend: !!form.querySelector('legend'),
                    fields: []
                };
                
                inputs.forEach(input => {
                    const field = {
                        type: input.type || input.tagName.toLowerCase(),
                        name: input.name,
                        id: input.id,
                        hasLabel: false,
                        hasAriaLabel: !!input.getAttribute('aria-label'),
                        hasAriaDescribedBy: !!input.getAttribute('aria-describedby'),
                        hasPlaceholder: !!input.placeholder,
                        required: input.required,
                        hasErrorMessage: false
                    };
                    
                    // Check for associated label
                    if (input.id) {
                        field.hasLabel = !!document.querySelector(`label[for="${input.id}"]`);
                    }
                    
                    // Check if wrapped in label
                    if (!field.hasLabel) {
                        field.hasLabel = !!input.closest('label');
                    }
                    
                    formData.fields.push(field);
                });
                
                results.push(formData);
            });
            
            return results;
        });
        
        // Analyze form accessibility
        const issues = [];
        forms.forEach((form, formIndex) => {
            form.fields.forEach((field, fieldIndex) => {
                if (!field.hasLabel && !field.hasAriaLabel) {
                    issues.push({
                        type: 'missing-label',
                        form: formIndex,
                        field: fieldIndex,
                        fieldType: field.type
                    });
                }
                
                if (field.required && !field.hasErrorMessage) {
                    issues.push({
                        type: 'missing-error-message',
                        form: formIndex,
                        field: fieldIndex,
                        fieldType: field.type
                    });
                }
            });
        });
        
        return { forms, issues };
    }
}

// ARIA implementation patterns
const ariaPatterns = {
    // Accessible modal
    modal: `
<div role="dialog" 
     aria-labelledby="modal-title" 
     aria-describedby="modal-description"
     aria-modal="true">
    <h2 id="modal-title">Modal Title</h2>
    <p id="modal-description">Modal description text</p>
    <button aria-label="Close modal">×</button>
</div>
    `,
    
    // Accessible tabs
    tabs: `
<div role="tablist" aria-label="Section navigation">
    <button role="tab" 
            aria-selected="true" 
            aria-controls="panel-1" 
            id="tab-1">
        Tab 1
    </button>
    <button role="tab" 
            aria-selected="false" 
            aria-controls="panel-2" 
            id="tab-2">
        Tab 2
    </button>
</div>
<div role="tabpanel" 
     id="panel-1" 
     aria-labelledby="tab-1">
    Panel 1 content
</div>
    `,
    
    // Accessible form
    form: `
<form>
    <fieldset>
        <legend>User Information</legend>
        
        <label for="name">
            Name
            <span aria-label="required">*</span>
        </label>
        <input id="name" 
               type="text" 
               required 
               aria-required="true"
               aria-describedby="name-error">
        <span id="name-error" 
              role="alert" 
              aria-live="polite"></span>
    </fieldset>
</form>
    `
};
```

### 5. Manual Testing Checklist

Create comprehensive manual testing guides:

**Manual Accessibility Checklist**

```markdown
## Manual Accessibility Testing Checklist

### 1. Keyboard Navigation
- [ ] Can access all interactive elements using Tab key
- [ ] Can activate buttons with Enter/Space
- [ ] Can navigate dropdowns with arrow keys
- [ ] Can escape modals with Esc key
- [ ] Focus indicator is always visible
- [ ] No keyboard traps exist
- [ ] Skip links work correctly
- [ ] Tab order is logical

### 2. Screen Reader Testing
- [ ] Page title is descriptive
- [ ] Headings create logical outline
- [ ] All images have appropriate alt text
- [ ] Form fields have labels
- [ ] Error messages are announced
- [ ] Dynamic content updates are announced
- [ ] Tables have proper headers
- [ ] Lists use semantic markup

### 3. Visual Testing
- [ ] Text can be resized to 200% without loss of functionality
- [ ] Color is not the only means of conveying information
- [ ] Focus indicators have sufficient contrast
- [ ] Content reflows at 320px width
- [ ] No horizontal scrolling at 320px
- [ ] Animations can be paused/stopped
- [ ] No content flashes more than 3 times per second

### 4. Cognitive Accessibility
- [ ] Instructions are clear and simple
- [ ] Error messages are helpful
- [ ] Forms can be completed without time limits
- [ ] Content is organized logically
- [ ] Navigation is consistent
- [ ] Important actions are reversible
- [ ] Help is available when needed

### 5. Mobile Accessibility
- [ ] Touch targets are at least 44x44 pixels
- [ ] Gestures have alternatives
- [ ] Device orientation works in both modes
- [ ] Virtual keyboard doesn't obscure inputs
- [ ] Pinch zoom is not disabled
```

### 6. Remediation Strategies

Provide fixes for common issues:

**Accessibility Fixes**

```javascript
// accessibility-fixes.js
class AccessibilityRemediator {
    applyFixes(violations) {
        violations.forEach(violation => {
            switch(violation.id) {
                case 'image-alt':
                    this.fixMissingAltText(violation.nodes);
                    break;
                case 'label':
                    this.fixMissingLabels(violation.nodes);
                    break;
                case 'color-contrast':
                    this.fixColorContrast(violation.nodes);
                    break;
                case 'heading-order':
                    this.fixHeadingOrder(violation.nodes);
                    break;
                case 'landmark-one-main':
                    this.fixLandmarks(violation.nodes);
                    break;
                default:
                    console.warn(`No automatic fix for: ${violation.id}`);
            }
        });
    }
    
    fixMissingAltText(nodes) {
        nodes.forEach(node => {
            const element = document.querySelector(node.target[0]);
            if (element && element.tagName === 'IMG') {
                // Decorative image
                if (this.isDecorativeImage(element)) {
                    element.setAttribute('alt', '');
                    element.setAttribute('role', 'presentation');
                } else {
                    // Generate meaningful alt text
                    const altText = this.generateAltText(element);
                    element.setAttribute('alt', altText);
                }
            }
        });
    }
    
    fixMissingLabels(nodes) {
        nodes.forEach(node => {
            const element = document.querySelector(node.target[0]);
            if (element && ['INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) {
                // Try to find nearby text
                const nearbyText = this.findNearbyLabelText(element);
                if (nearbyText) {
                    const label = document.createElement('label');
                    label.textContent = nearbyText;
                    label.setAttribute('for', element.id || this.generateId());
                    element.id = element.id || label.getAttribute('for');
                    element.parentNode.insertBefore(label, element);
                } else {
                    // Use placeholder as aria-label
                    if (element.placeholder) {
                        element.setAttribute('aria-label', element.placeholder);
                    }
                }
            }
        });
    }
    
    fixColorContrast(nodes) {
        nodes.forEach(node => {
            const element = document.querySelector(node.target[0]);
            if (element) {
                const styles = window.getComputedStyle(element);
                const foreground = styles.color;
                const background = this.getBackgroundColor(element);
                
                // Apply high contrast fixes
                element.style.setProperty('color', 'var(--high-contrast-text, #000)', 'important');
                element.style.setProperty('background-color', 'var(--high-contrast-bg, #fff)', 'important');
            }
        });
    }
    
    generateAltText(img) {
        // Use various strategies to generate alt text
        const strategies = [
            () => img.title,
            () => img.getAttribute('data-alt'),
            () => this.extractFromFilename(img.src),
            () => this.extractFromSurroundingText(img),
            () => 'Image'
        ];
        
        for (const strategy of strategies) {
            const text = strategy();
            if (text && text.trim()) {
                return text.trim();
            }
        }
        
        return 'Image';
    }
}

// React accessibility components
import React from 'react';

// Accessible button component
const AccessibleButton = ({ 
    children, 
    onClick, 
    ariaLabel, 
    ariaPressed,
    disabled,
    ...props 
}) => {
    return (
        <button
            onClick={onClick}
            aria-label={ariaLabel}
            aria-pressed={ariaPressed}
            disabled={disabled}
            className="accessible-button"
            {...props}
        >
            {children}
        </button>
    );
};

// Live region for announcements
const LiveRegion = ({ message, politeness = 'polite' }) => {
    return (
        <div
            role="status"
            aria-live={politeness}
            aria-atomic="true"
            className="sr-only"
        >
            {message}
        </div>
    );
};

// Skip navigation component
const SkipNav = () => {
    return (
        <a href="#main-content" className="skip-nav">
            Skip to main content
        </a>
    );
};
```

### 7. CI/CD Integration

Integrate accessibility testing into pipelines:

**CI/CD Accessibility Pipeline**

```yaml
# .github/workflows/accessibility.yml
name: Accessibility Tests

on: [push, pull_request]

jobs:
  a11y-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Build application
      run: npm run build
    
    - name: Start server
      run: |
        npm start &
        npx wait-on http://localhost:3000
    
    - name: Run axe accessibility tests
      run: npm run test:a11y
    
    - name: Run pa11y tests
      run: |
        npx pa11y http://localhost:3000 \
          --reporter cli \
          --standard WCAG2AA \
          --threshold 0
    
    - name: Run Lighthouse CI
      run: |
        npm install -g @lhci/cli
        lhci autorun --config=lighthouserc.json
    
    - name: Upload accessibility report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: accessibility-report
        path: |
          a11y-report.html
          lighthouse-report.html
```

**Pre-commit Hook**

```bash
#!/bin/bash
# .husky/pre-commit

# Run accessibility tests on changed components
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(jsx?|tsx?)$')

if [ -n "$CHANGED_FILES" ]; then
    echo "Running accessibility tests on changed files..."
    npm run test:a11y -- $CHANGED_FILES
    
    if [ $? -ne 0 ]; then
        echo "❌ Accessibility tests failed. Please fix issues before committing."
        exit 1
    fi
fi
```

### 8. Accessibility Reporting

Generate comprehensive reports:

**Report Generator**

```javascript
// accessibility-report-generator.js
class AccessibilityReportGenerator {
    generateHTMLReport(auditResults) {
        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessibility Audit Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .summary { background: #f0f0f0; padding: 20px; border-radius: 8px; }
        .score { font-size: 48px; font-weight: bold; }
        .score.good { color: #0f0; }
        .score.warning { color: #fa0; }
        .score.poor { color: #f00; }
        .violation { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        .violation.critical { border-color: #f00; background: #fee; }
        .violation.serious { border-color: #fa0; background: #ffe; }
        .code { background: #f5f5f5; padding: 10px; font-family: monospace; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    </style>
</head>
<body>
    <h1>Accessibility Audit Report</h1>
    <p>Generated: ${new Date().toLocaleString()}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <div class="score ${this.getScoreClass(auditResults.summary.score)}">
            Score: ${auditResults.summary.score}/100
        </div>
        <p>WCAG ${auditResults.summary.wcagCompliance} Compliance</p>
        
        <h3>Violations by Impact</h3>
        <table>
            <tr>
                <th>Impact</th>
                <th>Count</th>
            </tr>
            ${Object.entries(auditResults.summary.violationsByImpact)
                .map(([impact, count]) => `
                    <tr>
                        <td>${impact}</td>
                        <td>${count}</td>
                    </tr>
                `).join('')}
        </table>
    </div>
    
    <h2>Detailed Violations</h2>
    ${auditResults.violations.map(violation => `
        <div class="violation ${violation.impact}">
            <h3>${violation.help}</h3>
            <p><strong>Rule:</strong> ${violation.id}</p>
            <p><strong>Impact:</strong> ${violation.impact}</p>
            <p>${violation.description}</p>
            
            <h4>Affected Elements (${violation.nodes.length})</h4>
            ${violation.nodes.map(node => `
                <div class="code">
                    <strong>Element:</strong> ${this.escapeHtml(node.html)}<br>
                    <strong>Selector:</strong> ${node.target.join(' ')}<br>
                    <strong>Fix:</strong> ${node.failureSummary}
                </div>
            `).join('')}
            
            <p><a href="${violation.helpUrl}" target="_blank">Learn more</a></p>
        </div>
    `).join('')}
    
    <h2>Manual Testing Required</h2>
    <ul>
        <li>Test with screen readers (NVDA, JAWS, VoiceOver)</li>
        <li>Test keyboard navigation thoroughly</li>
        <li>Test with browser zoom at 200%</li>
        <li>Test with Windows High Contrast mode</li>
        <li>Review content for plain language</li>
    </ul>
</body>
</html>
        `;
        
        return html;
    }
    
    generateJSONReport(auditResults) {
        return {
            metadata: {
                timestamp: new Date().toISOString(),
                url: auditResults.url,
                wcagVersion: '2.1',
                level: 'AA'
            },
            summary: auditResults.summary,
            violations: auditResults.violations.map(v => ({
                id: v.id,
                impact: v.impact,
                help: v.help,
                count: v.nodes.length,
                elements: v.nodes.map(n => ({
                    target: n.target.join(' '),
                    html: n.html
                }))
            })),
            passes: auditResults.passes,
            incomplete: auditResults.incomplete
        };
    }
}
```

## Output Format

1. **Accessibility Score**: Overall compliance score with WCAG levels
1. **Violation Report**: Detailed list of issues with severity and fixes
1. **Test Results**: Automated and manual test outcomes
1. **Remediation Guide**: Step-by-step fixes for each issue
1. **Code Examples**: Accessible component implementations
1. **Testing Scripts**: Reusable test suites for CI/CD
1. **Checklist**: Manual testing checklist for QA
1. **Progress Tracking**: Accessibility improvement metrics

Focus on creating inclusive experiences that work for all users, regardless of their abilities or assistive technologies.

______________________________________________________________________

## Security Considerations

### Access Control for Monitoring Data

- **Authentication Required**: Protect monitoring dashboards with SSO
- **RBAC for Metrics**: Implement role-based access to sensitive metrics
- **Audit Logging**: Log access to monitoring systems

### Sensitive Data in Logs

- **PII Redaction**: Automatically redact sensitive data from logs
- **Secret Filtering**: Never log secrets, tokens, or passwords
- **Log Sanitization**: Implement pre-processing to remove sensitive fields

```python
# Example: Log sanitization
import re
from structlog.processors import JSONRenderer

def sanitize_logs(logger, name, event_dict):
    """Remove sensitive data from logs"""
    sensitive_patterns = {
        'password': r'password["']?\s*[:=]\s*["']?[^"'}\s]+',
        'api_key': r'api[_-]?key["']?\s*[:=]\s*["']?[^"'}\s]+',
        'token': r'token["']?\s*[:=]\s*["']?[^"'}\s]+',
    }

    message = str(event_dict.get('event', ''))
    for name, pattern in sensitive_patterns.items():
        message = re.sub(pattern, f'{name}=REDACTED', message, flags=re.IGNORECASE)

    event_dict['event'] = message
    return event_dict
```

### Metrics Security

- **Avoid Sensitive Metrics**: Don't expose PII in metric labels
- **Cardinality Limits**: Prevent cardinality explosions from untrusted inputs
- **Secure Metric Endpoints**: Protect Prometheus/metric endpoints

### Monitoring System Security

- **TLS for Transport**: Encrypt data in transit to monitoring backends
- **Secure Storage**: Encrypt stored logs and metrics
- **Retention Policies**: Define and enforce data retention limits

### Alert Security

- **Secure Alert Channels**: Use encrypted channels (Slack, PagerDuty)
- **Alert Data Filtering**: Don't include sensitive data in alerts
- **Alert Access Control**: Restrict who can modify alert configurations

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Monitoring Configuration Testing

```python
# Test Prometheus rules
import yaml
from promtool import validate_rules


def test_prometheus_rules_valid():
    with open("prometheus-rules.yaml") as f:
        rules = yaml.safe_load(f)

    # Validate syntax
    result = validate_rules(rules)
    assert result.is_valid


# Test alert fires correctly
def test_high_cpu_alert_fires():
    # Simulate high CPU metrics
    push_metric("cpu_usage", 95)

    # Wait for alert evaluation
    time.sleep(30)

    # Check alert status
    alerts = get_firing_alerts()
    assert any(a["alertname"] == "HighCPUUsage" for a in alerts)
```

### Log Parsing Testing

```python
# Test log processors
def test_log_parsing():
    log_line = "2025-01-15 12:00:00 INFO user_id=123 action=login status=success"

    parsed = parse_log_line(log_line)

    assert parsed["timestamp"] == "2025-01-15 12:00:00"
    assert parsed["level"] == "INFO"
    assert parsed["user_id"] == "123"
    assert parsed["action"] == "login"


def test_sensitive_data_redaction():
    log_line = "password=secret123 api_key=sk-1234567890"

    redacted = redact_sensitive_data(log_line)

    assert "secret123" not in redacted
    assert "sk-1234567890" not in redacted
    assert "password=REDACTED" in redacted
```

### Dashboard Testing

```python
# Test Grafana dashboard JSON
import json


def test_grafana_dashboard_valid():
    with open("dashboard.json") as f:
        dashboard = json.load(f)

    # Validate structure
    assert "title" in dashboard
    assert "panels" in dashboard
    assert len(dashboard["panels"]) > 0

    # Validate queries
    for panel in dashboard["panels"]:
        if "targets" in panel:
            for target in panel["targets"]:
                assert "expr" in target  # Prometheus query exists
```

### Tracing Validation

```python
# Test distributed trace completeness
def test_trace_spans_complete():
    # Make request that should create trace
    response = requests.get("http://app/api/users/123")

    # Retrieve trace
    trace = get_trace_by_request_id(response.headers["X-Request-ID"])

    # Validate all expected spans exist
    span_names = [span["name"] for span in trace["spans"]]
    assert "http.request" in span_names
    assert "db.query" in span_names
    assert "cache.get" in span_names

    # Validate parent-child relationships
    root_span = trace["spans"][0]
    assert all(s["parent_id"] == root_span["id"] for s in trace["spans"][1:])
```

______________________________________________________________________

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue 1: Configuration Errors**

**Symptoms:**

- Tool fails to start or execute
- Missing required parameters
- Invalid configuration values

**Solutions:**

1. Verify all required environment variables are set
1. Check configuration file syntax (YAML, JSON)
1. Review logs for specific error messages
1. Validate file paths and permissions

______________________________________________________________________

**Issue 2: Permission Denied Errors**

**Symptoms:**

- Cannot access files or directories
- Operations fail with permission errors
- Insufficient privileges

**Solutions:**

1. Check file/directory permissions: `ls -la`
1. Run with appropriate user privileges
1. Verify user is in required groups: `groups`
1. Use `sudo` for privileged operations when necessary

______________________________________________________________________

**Issue 3: Resource Not Found**

**Symptoms:**

- "File not found" or "Resource not found" errors
- Missing dependencies
- Broken references

**Solutions:**

1. Verify resource paths are correct (use absolute paths)
1. Check that required files exist before execution
1. Ensure dependencies are installed
1. Review environment-specific configurations

______________________________________________________________________

**Issue 4: Timeout or Performance Issues**

**Symptoms:**

- Operations taking longer than expected
- Timeout errors
- Resource exhaustion (CPU, memory, disk)

**Solutions:**

1. Increase timeout values in configuration
1. Optimize queries or operations
1. Add pagination for large datasets
1. Monitor resource usage: `top`, `htop`, `docker stats`
1. Implement caching where appropriate

______________________________________________________________________

### Getting Help

If issues persist after trying these solutions:

1. **Check Logs**: Review application and system logs for detailed error messages
1. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
1. **Consult Documentation**: Review related tool documentation in this directory
1. **Contact Support**: Reach out with:
   - Error messages and stack traces
   - Steps to reproduce
   - Environment details (OS, versions, configuration)
   - Relevant log excerpts

______________________________________________________________________
