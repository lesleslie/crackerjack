______________________________________________________________________

title: Frontend Bundle Analyze
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXCFPKR8SGCRGWFJMJ9E7
  category: development/frontend

______________________________________________________________________

## Frontend Bundle Analysis

You are a frontend performance expert specializing in bundle analysis, optimization, and performance monitoring for modern web applications. Analyze bundle composition, identify optimization opportunities, and implement performance improvements.

## Context

The user needs comprehensive frontend bundle analysis including size analysis, dependency auditing, code splitting optimization, and performance monitoring setup for web applications.

## Requirements

$ARGUMENTS

## Instructions

### 1. Bundle Analysis

Use Task tool with subagent_type="frontend-developer" for bundle analysis:

Prompt: "Analyze frontend bundle for: $ARGUMENTS. Focus on:

1. Bundle size analysis and composition breakdown
1. Dependency analysis and tree shaking opportunities
1. Code splitting and lazy loading optimization
1. Asset optimization and compression strategies
1. Performance metrics and Core Web Vitals assessment"

### 2. Performance Optimization

Use Task tool with subagent_type="observability-incident-lead" for optimization strategies:

Prompt: "Optimize frontend performance for: $ARGUMENTS. Include:

1. Bundle size reduction techniques
1. Critical resource loading optimization
1. Runtime performance improvements
1. Caching strategy implementation
1. Performance monitoring and metrics tracking"

### 3. Bundle Analysis Implementation

**Webpack Bundle Analyzer Configuration**

```javascript
// webpack.analyze.js
const path = require('path');
const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer');
const CompressionPlugin = require('compression-webpack-plugin');

module.exports = {
  mode: 'production',
  entry: './src/index.js',

  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].[contenthash].js',
    chunkFilename: '[name].[contenthash].chunk.js',
    clean: true,
  },

  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
        },
        common: {
          name: 'common',
          minChunks: 2,
          chunks: 'all',
          enforce: true,
        },
      },
    },
    usedExports: true,
    sideEffects: false,
  },

  plugins: [
    new BundleAnalyzerPlugin({
      analyzerMode: 'static',
      openAnalyzer: false,
      reportFilename: 'bundle-report.html',
      generateStatsFile: true,
      statsFilename: 'bundle-stats.json',
    }),

    new CompressionPlugin({
      filename: '[path][base].gz',
      algorithm: 'gzip',
      test: /\.(js|css|html|svg)$/,
      threshold: 8192,
      minRatio: 0.8,
    }),
  ],

  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              ['@babel/preset-env', {
                modules: false,
                useBuiltIns: 'usage',
                corejs: 3,
              }],
            ],
          },
        },
      },
      {
        test: /\.css$/,
        use: [
          'style-loader',
          'css-loader',
          {
            loader: 'postcss-loader',
            options: {
              postcssOptions: {
                plugins: [
                  require('cssnano')({
                    preset: 'default',
                  }),
                ],
              },
            },
          },
        ],
      },
    ],
  },
};
```

**Bundle Analysis Script**

```javascript
// analyze-bundle.js
const fs = require('fs');
const path = require('path');
const gzipSize = require('gzip-size');

class BundleAnalyzer {
  constructor(statsPath) {
    this.stats = JSON.parse(fs.readFileSync(statsPath, 'utf8'));
    this.analysis = {};
  }

  async analyze() {
    this.analysis = {
      overview: this.getOverview(),
      assets: await this.analyzeAssets(),
      chunks: this.analyzeChunks(),
      modules: this.analyzeModules(),
      dependencies: this.analyzeDependencies(),
      recommendations: this.generateRecommendations(),
    };

    return this.analysis;
  }

  getOverview() {
    const assets = this.stats.assets || [];
    const totalSize = assets.reduce((sum, asset) => sum + asset.size, 0);
    const jsAssets = assets.filter(asset => asset.name.endsWith('.js'));
    const cssAssets = assets.filter(asset => asset.name.endsWith('.css'));

    return {
      totalAssets: assets.length,
      totalSize: this.formatBytes(totalSize),
      jsSize: this.formatBytes(jsAssets.reduce((sum, asset) => sum + asset.size, 0)),
      cssSize: this.formatBytes(cssAssets.reduce((sum, asset) => sum + asset.size, 0)),
      chunkCount: (this.stats.chunks || []).length,
      moduleCount: (this.stats.modules || []).length,
    };
  }

  async analyzeAssets() {
    const assets = this.stats.assets || [];
    const analysis = [];

    for (const asset of assets) {
      const filePath = path.join('dist', asset.name);
      let gzippedSize = 0;

      try {
        if (fs.existsSync(filePath)) {
          gzippedSize = await gzipSize.file(filePath);
        }
      } catch (error) {
        console.warn(`Could not analyze ${asset.name}:`, error.message);
      }

      analysis.push({
        name: asset.name,
        size: asset.size,
        sizeFormatted: this.formatBytes(asset.size),
        gzippedSize,
        gzippedSizeFormatted: this.formatBytes(gzippedSize),
        compressionRatio: gzippedSize > 0 ? ((asset.size - gzippedSize) / asset.size * 100).toFixed(1) + '%' : '0%',
        type: this.getAssetType(asset.name),
        critical: this.isCriticalAsset(asset.name),
      });
    }

    return analysis.sort((a, b) => b.size - a.size);
  }

  analyzeChunks() {
    const chunks = this.stats.chunks || [];

    return chunks.map(chunk => ({
      id: chunk.id,
      name: chunk.name || `chunk-${chunk.id}`,
      size: chunk.size,
      sizeFormatted: this.formatBytes(chunk.size),
      files: chunk.files || [],
      modules: chunk.modules?.length || 0,
      entry: chunk.entry || false,
      initial: chunk.initial || false,
      reason: chunk.reason || 'Unknown',
    })).sort((a, b) => b.size - a.size);
  }

  analyzeModules() {
    const modules = this.stats.modules || [];
    const moduleAnalysis = {};

    // Group modules by package
    modules.forEach(module => {
      const name = this.getModuleName(module.name || module.identifier);
      const packageName = this.getPackageName(name);

      if (!moduleAnalysis[packageName]) {
        moduleAnalysis[packageName] = {
          name: packageName,
          size: 0,
          modules: [],
        };
      }

      moduleAnalysis[packageName].size += module.size || 0;
      moduleAnalysis[packageName].modules.push({
        name,
        size: module.size || 0,
        sizeFormatted: this.formatBytes(module.size || 0),
      });
    });

    // Convert to array and sort
    return Object.values(moduleAnalysis)
      .map(pkg => ({
        ...pkg,
        sizeFormatted: this.formatBytes(pkg.size),
        moduleCount: pkg.modules.length,
      }))
      .sort((a, b) => b.size - a.size);
  }

  analyzeDependencies() {
    const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const dependencies = { ...packageJson.dependencies, ...packageJson.devDependencies };
    const moduleAnalysis = this.analyzeModules();

    return Object.keys(dependencies).map(dep => {
      const moduleInfo = moduleAnalysis.find(m => m.name === dep || m.name.startsWith(dep + '/'));

      return {
        name: dep,
        version: dependencies[dep],
        bundleSize: moduleInfo ? moduleInfo.size : 0,
        bundleSizeFormatted: moduleInfo ? moduleInfo.sizeFormatted : '0 B',
        included: !!moduleInfo,
        type: packageJson.dependencies[dep] ? 'production' : 'development',
      };
    }).sort((a, b) => b.bundleSize - a.bundleSize);
  }

  generateRecommendations() {
    const recommendations = [];
    const assets = this.analysis.assets || [];
    const modules = this.analysis.modules || [];

    // Large bundle warning
    const totalJSSize = assets
      .filter(a => a.type === 'js')
      .reduce((sum, a) => sum + a.size, 0);

    if (totalJSSize > 1024 * 1024) { // > 1MB
      recommendations.push({
        type: 'warning',
        category: 'Bundle Size',
        message: `Total JavaScript bundle size is ${this.formatBytes(totalJSSize)}. Consider code splitting.`,
        impact: 'high',
        effort: 'medium',
      });
    }

    // Large dependencies
    const largeDeps = modules.filter(m => m.size > 100 * 1024); // > 100KB
    if (largeDeps.length > 0) {
      recommendations.push({
        type: 'info',
        category: 'Dependencies',
        message: `Large dependencies detected: ${largeDeps.map(d => d.name).join(', ')}`,
        impact: 'medium',
        effort: 'low',
      });
    }

    // Duplicate code detection
    const duplicateModules = this.findDuplicateModules();
    if (duplicateModules.length > 0) {
      recommendations.push({
        type: 'warning',
        category: 'Code Splitting',
        message: `Potential duplicate modules detected: ${duplicateModules.join(', ')}`,
        impact: 'medium',
        effort: 'high',
      });
    }

    return recommendations;
  }

  formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  getAssetType(name) {
    if (name.endsWith('.js')) return 'js';
    if (name.endsWith('.css')) return 'css';
    if (name.match(/\.(png|jpg|jpeg|gif|svg|webp)$/)) return 'image';
    if (name.match(/\.(woff|woff2|ttf|eot)$/)) return 'font';
    return 'other';
  }

  isCriticalAsset(name) {
    return name.includes('main') || name.includes('app') || name.includes('vendor');
  }

  getModuleName(identifier) {
    return identifier.replace(/^\.\//, '').replace(/\?.*$/, '');
  }

  getPackageName(name) {
    if (name.startsWith('node_modules/')) {
      const parts = name.split('/');
      return parts[1].startsWith('@') ? `${parts[1]}/${parts[2]}` : parts[1];
    }
    return name.split('/')[0] || 'app';
  }

  findDuplicateModules() {
    // Implementation for duplicate module detection
    return [];
  }
}

// Usage
async function analyzeBundles() {
  const analyzer = new BundleAnalyzer('./dist/bundle-stats.json');
  const analysis = await analyzer.analyze();

  // Generate report
  const report = {
    timestamp: new Date().toISOString(),
    ...analysis,
  };

  fs.writeFileSync('./bundle-analysis.json', JSON.stringify(report, null, 2));

  console.log('📊 Bundle Analysis Complete');
  console.log(`📦 Total Size: ${analysis.overview.totalSize}`);
  console.log(`🟨 JavaScript: ${analysis.overview.jsSize}`);
  console.log(`🟦 CSS: ${analysis.overview.cssSize}`);
  console.log(`⚠️  Recommendations: ${analysis.recommendations.length}`);

  return report;
}

if (require.main === module) {
  analyzeBundles().catch(console.error);
}

module.exports = { BundleAnalyzer, analyzeBundles };
```

### 4. Performance Optimization Strategies

**Code Splitting Implementation**

```javascript
// code-splitting-config.js
import { lazy, Suspense } from 'react';

// Route-based code splitting
const HomePage = lazy(() => import('./pages/HomePage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));

// Component-based code splitting
const HeavyChart = lazy(() => import('./components/HeavyChart'));
const DataTable = lazy(() => import('./components/DataTable'));

// Conditional loading
const AdminPanel = lazy(() =>
  import('./components/AdminPanel').then(module => ({
    default: module.AdminPanel
  }))
);

// Dynamic imports with error handling
async function loadFeature(featureName) {
  try {
    const module = await import(`./features/${featureName}`);
    return module.default;
  } catch (error) {
    console.error(`Failed to load feature ${featureName}:`, error);
    return null;
  }
}

// Progressive loading wrapper
function ProgressiveLoader({ children, fallback, error }) {
  return (
    <Suspense fallback={fallback || <div>Loading...</div>}>
      {children}
    </Suspense>
  );
}
```

**Resource Optimization**

```javascript
// resource-optimization.js
class ResourceOptimizer {
  constructor() {
    this.preloadedResources = new Set();
    this.observers = new Map();
  }

  // Preload critical resources
  preloadCriticalResources() {
    const criticalResources = [
      { href: '/api/user', as: 'fetch' },
      { href: '/styles/critical.css', as: 'style' },
      { href: '/fonts/primary.woff2', as: 'font', type: 'font/woff2', crossorigin: true },
    ];

    criticalResources.forEach(resource => {
      if (!this.preloadedResources.has(resource.href)) {
        this.preloadResource(resource);
        this.preloadedResources.add(resource.href);
      }
    });
  }

  preloadResource({ href, as, type, crossorigin }) {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.href = href;
    link.as = as;

    if (type) link.type = type;
    if (crossorigin) link.crossOrigin = crossorigin;

    document.head.appendChild(link);
  }

  // Lazy load images with Intersection Observer
  setupLazyLoading() {
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.classList.remove('lazy');
          imageObserver.unobserve(img);
        }
      });
    });

    document.querySelectorAll('img[data-src]').forEach(img => {
      imageObserver.observe(img);
    });

    this.observers.set('images', imageObserver);
  }

  // Prefetch next page resources
  prefetchRoute(route) {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = route;
    document.head.appendChild(link);
  }

  // Monitor performance metrics
  trackPerformanceMetrics() {
    // Core Web Vitals tracking
    import('web-vitals').then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
      getCLS(this.sendMetric);
      getFID(this.sendMetric);
      getFCP(this.sendMetric);
      getLCP(this.sendMetric);
      getTTFB(this.sendMetric);
    });
  }

  sendMetric(metric) {
    // Send metrics to analytics
    console.log('Performance Metric:', metric);

    // Example: Send to analytics service
    navigator.sendBeacon('/api/metrics', JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      timestamp: Date.now(),
      url: window.location.href,
    }));
  }
}

// Initialize optimizer
const optimizer = new ResourceOptimizer();
optimizer.preloadCriticalResources();
optimizer.setupLazyLoading();
optimizer.trackPerformanceMetrics();
```

### 5. Performance Monitoring

**Bundle Monitoring Dashboard**

```html
<!-- bundle-dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Bundle Performance Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: system-ui; margin: 0; padding: 20px; background: #f5f5f5; }
        .dashboard { max-width: 1200px; margin: 0 auto; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .metric-value { font-size: 2em; font-weight: bold; color: #333; }
        .metric-label { color: #666; margin-top: 5px; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <div class="dashboard">
        <h1>Bundle Performance Dashboard</h1>

        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value" id="bundleSize">-</div>
                <div class="metric-label">Total Bundle Size</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="gzipSize">-</div>
                <div class="metric-label">Gzipped Size</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="chunkCount">-</div>
                <div class="metric-label">Chunk Count</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="loadTime">-</div>
                <div class="metric-label">Load Time (P95)</div>
            </div>
        </div>

        <div class="chart-container">
            <h3>Bundle Size Trend</h3>
            <canvas id="sizeChart"></canvas>
        </div>

        <div class="chart-container">
            <h3>Dependency Breakdown</h3>
            <canvas id="dependencyChart"></canvas>
        </div>
    </div>

    <script>
        class BundleDashboard {
            constructor() {
                this.sizeChart = null;
                this.dependencyChart = null;
                this.init();
            }

            async init() {
                await this.loadBundleData();
                this.setupCharts();
                this.startRealTimeUpdates();
            }

            async loadBundleData() {
                try {
                    const response = await fetch('/api/bundle-stats');
                    this.data = await response.json();
                    this.updateMetrics();
                } catch (error) {
                    console.error('Failed to load bundle data:', error);
                }
            }

            updateMetrics() {
                document.getElementById('bundleSize').textContent = this.data.overview.totalSize;
                document.getElementById('gzipSize').textContent = this.data.overview.gzippedSize || 'N/A';
                document.getElementById('chunkCount').textContent = this.data.overview.chunkCount;
                document.getElementById('loadTime').textContent = this.data.performance?.loadTime || 'N/A';
            }

            setupCharts() {
                // Bundle size trend chart
                const sizeCtx = document.getElementById('sizeChart').getContext('2d');
                this.sizeChart = new Chart(sizeCtx, {
                    type: 'line',
                    data: {
                        labels: this.data.history?.map(h => h.date) || [],
                        datasets: [{
                            label: 'Bundle Size (KB)',
                            data: this.data.history?.map(h => h.size / 1024) || [],
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.1
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Size (KB)'
                                }
                            }
                        }
                    }
                });

                // Dependency breakdown chart
                const depCtx = document.getElementById('dependencyChart').getContext('2d');
                this.dependencyChart = new Chart(depCtx, {
                    type: 'doughnut',
                    data: {
                        labels: this.data.modules?.slice(0, 10).map(m => m.name) || [],
                        datasets: [{
                            data: this.data.modules?.slice(0, 10).map(m => m.size) || [],
                            backgroundColor: [
                                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                                '#9966FF', '#FF9F40', '#C9CBCF', '#4BC0C0',
                                '#FF6384', '#36A2EB'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'right'
                            }
                        }
                    }
                });
            }

            startRealTimeUpdates() {
                setInterval(async () => {
                    await this.loadBundleData();
                    this.updateCharts();
                }, 30000); // Update every 30 seconds
            }

            updateCharts() {
                if (this.sizeChart && this.data.history) {
                    this.sizeChart.data.labels = this.data.history.map(h => h.date);
                    this.sizeChart.data.datasets[0].data = this.data.history.map(h => h.size / 1024);
                    this.sizeChart.update();
                }

                if (this.dependencyChart && this.data.modules) {
                    this.dependencyChart.data.labels = this.data.modules.slice(0, 10).map(m => m.name);
                    this.dependencyChart.data.datasets[0].data = this.data.modules.slice(0, 10).map(m => m.size);
                    this.dependencyChart.update();
                }
            }
        }

        // Initialize dashboard
        new BundleDashboard();
    </script>
</body>
</html>
```

## Output Format

1. **Bundle Analysis Report**: Comprehensive size and composition analysis
1. **Performance Metrics**: Core Web Vitals and loading performance data
1. **Optimization Recommendations**: Prioritized improvements with impact assessment
1. **Code Splitting Strategy**: Implementation plan for bundle optimization
1. **Resource Optimization**: Critical resource loading and caching strategies
1. **Dependency Analysis**: Third-party library impact and alternatives
1. **Performance Monitoring**: Real-time monitoring setup and alerting
1. **Implementation Guide**: Step-by-step optimization implementation
1. **Before/After Comparison**: Performance improvement measurements
1. **Ongoing Maintenance**: Long-term bundle health monitoring

Focus on providing actionable bundle optimization strategies that significantly improve frontend performance while maintaining development efficiency.

Target: $ARGUMENTS

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

- Implement proper authentication mechanisms for accessing this tool
- Use role-based access control (RBAC) to restrict sensitive operations
- Enable audit logging for all security-relevant actions

### Data Protection

- Encrypt sensitive data at rest and in transit
- Implement proper secrets management (see `secrets-management.md`)
- Follow data minimization principles

### Access Control

- Follow principle of least privilege when granting permissions
- Use dedicated service accounts with minimal required permissions
- Implement multi-factor authentication for production access

### Secure Configuration

- Avoid hardcoding credentials in code or configuration files
- Use environment variables or secure vaults for sensitive configuration
- Regularly rotate credentials and API keys

### Monitoring & Auditing

- Log security-relevant events (authentication, authorization failures, data access)
- Implement alerting for suspicious activities
- Maintain immutable audit trails for compliance

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# Example unit tests
import pytest


def test_basic_functionality():
    result = function_under_test(input_value)
    assert result == expected_output


def test_error_handling():
    with pytest.raises(ValueError):
        function_under_test(invalid_input)


def test_edge_cases():
    assert function_under_test([]) == []
    assert function_under_test(None) is None
```

### Integration Testing

```python
# Integration test example
@pytest.mark.integration
def test_end_to_end_workflow():
    # Setup
    resource = create_resource()

    # Execute workflow
    result = process_resource(resource)

    # Verify
    assert result.status == "success"
    assert result.output is not None

    # Cleanup
    delete_resource(resource.id)
```

### Validation

```bash
# Validate configuration files
yamllint config/*.yaml

# Validate scripts
shellcheck scripts/*.sh

# Run linters
pylint src/
flake8 src/
mypy src/
```

### CI/CD Testing

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3
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
