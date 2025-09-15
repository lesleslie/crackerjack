# Code Cleaner Backup System

## Overview

The crackerjack code cleaner now includes a comprehensive backup system that provides automatic backup and restoration capabilities to protect package files during cleaning operations. This ensures that users never lose code even if the cleaning process encounters errors.

## Key Features

### 🛡️ Pre-Cleaning Backup System

- **Complete Package Backup**: Creates backup of ALL package files before any cleaning starts
- **Secure Storage**: Uses secure temporary directories with proper permissions
- **Atomic Operations**: All file operations are atomic to prevent corruption
- **Integrity Validation**: SHA-256 checksums ensure backup completeness and integrity

### 🔄 Automatic Error Recovery

- **Smart Error Detection**: Detects ANY error during cleaning process
- **Automatic Restoration**: Immediately restores all files from backup on error
- **Complete Recovery**: Either all files are cleaned successfully or all are restored
- **No Data Loss**: Guarantees that no code is ever lost during cleaning

### 📦 Backup Management

- **Timestamped Backups**: Each backup has unique timestamp-based identifier
- **Automatic Cleanup**: Successful cleanings automatically remove backup files
- **Failure Preservation**: Failed cleanings preserve backups for manual inspection
- **Space Efficient**: Only creates backups when actually needed

### 🔍 Security & Validation

- **Path Validation**: All paths validated against security policies
- **Checksum Verification**: File integrity verified before and after operations
- **Secure Permissions**: Backup directories created with restricted access
- **Comprehensive Logging**: All backup operations logged for audit trail

## Implementation Architecture

### Core Components

1. **`PackageBackupService`** (`crackerjack/services/backup_service.py`)

   - Handles all backup and restoration operations
   - Provides backup validation and integrity checking
   - Manages secure temporary directory creation

1. **`CodeCleaner` Enhanced** (`crackerjack/code_cleaner.py`)

   - New `clean_files_with_backup()` method with comprehensive backup protection
   - Legacy `clean_files()` method preserved for compatibility
   - `PackageCleaningResult` for detailed backup-aware results

1. **API Integration** (`crackerjack/api.py`)

   - High-level `clean_code()` function with `safe_mode` parameter
   - Backward compatible with existing code
   - Comprehensive result reporting

### Data Models

```python
@dataclass
class BackupMetadata:
    backup_id: str  # Unique backup identifier
    timestamp: datetime  # Backup creation time
    package_directory: Path  # Original package directory
    backup_directory: Path  # Backup storage location
    total_files: int  # Number of files backed up
    total_size: int  # Total backup size in bytes
    checksum: str  # Overall backup checksum
    file_checksums: dict[str, str]  # Individual file checksums


@dataclass
class PackageCleaningResult:
    total_files: int  # Total files processed
    successful_files: int  # Successfully cleaned files
    failed_files: int  # Files that failed cleaning
    file_results: list[CleaningResult]  # Detailed per-file results
    backup_metadata: BackupMetadata | None  # Backup information
    backup_restored: bool  # Whether backup was restored
    overall_success: bool  # Overall operation success
```

## Usage Examples

### Safe Mode (Recommended)

```python
from crackerjack import clean_code
from pathlib import Path

# Use safe mode with comprehensive backup protection
result = clean_code(
    project_path=Path("my_project"),
    safe_mode=True,  # This is the default
)

if isinstance(result, PackageCleaningResult):
    if result.overall_success:
        print(f"✅ Successfully cleaned {result.successful_files} files")
    else:
        print(f"❌ Cleaning failed, {result.backup_restored=}")
        if result.backup_metadata:
            print(f"📦 Backup available: {result.backup_metadata.backup_directory}")
```

### Direct CodeCleaner Usage

```python
from crackerjack.code_cleaner import CodeCleaner
from rich.console import Console

console = Console()
cleaner = CodeCleaner(console=console)

# Safe cleaning with automatic backup
result = cleaner.clean_files_with_backup(Path("my_package"))

if not result.overall_success and result.backup_metadata:
    # Emergency restoration if needed
    cleaner.restore_from_backup_metadata(result.backup_metadata)
```

### Legacy Mode (Compatibility)

```python
# Legacy mode without backup protection
result = clean_code(
    project_path=Path("my_project"),
    safe_mode=False,  # Not recommended
)

# Returns list[CleaningResult] instead of PackageCleaningResult
```

## Safety Guarantees

### Complete Protection

- **No Data Loss**: Files are never lost, even during system crashes
- **Atomic Operations**: Either all files cleaned or all restored
- **Integrity Validation**: Checksums ensure no corruption
- **Error Recovery**: Automatic restoration on any error

### Error Scenarios Handled

- File permission denied during writing
- Disk space exhaustion
- System crashes or interruptions
- Memory errors during processing
- Network interruptions (for networked storage)
- Any unexpected exceptions

### Backup Workflow

1. **Pre-Cleaning Phase**

   - Scan package directory for all Python files
   - Create secure backup directory with unique ID
   - Copy all files with checksum calculation
   - Validate backup integrity

1. **Cleaning Phase**

   - Apply cleaning operations to all files
   - Collect success/failure status for each file
   - Track any errors or exceptions

1. **Post-Cleaning Phase**

   - **Success**: Clean up backup directory
   - **Failure**: Restore all files from backup, preserve backup

## Integration Points

### Command Line Integration

The backup system integrates seamlessly with existing crackerjack workflows:

```bash
# Safe mode is used by default in code cleaning operations
python -m crackerjack -x  # Uses backup protection

# AI agent auto-fixing also benefits from backup protection
python -m crackerjack --ai-agent -x
```

### MCP Server Integration

The backup system works with the MCP server for AI agent workflows:

```python
# MCP tools automatically use safe mode for code cleaning
result = await client.call_tool(
    "clean_package_files",
    {
        "safe_mode": True  # Default
    },
)
```

## Configuration

### Backup Storage

- **Default Location**: System temporary directory (`/tmp/crackerjack_backups`)
- **Customization**: Can be configured via `PackageBackupService.backup_root`
- **Permissions**: Backup directories created with `0o700` (owner-only access)

### File Filtering

Backup system only processes main package files:

- **Included**: `.py` files in main package directories
- **Excluded**: Tests, examples, build artifacts, cache directories

### Security Settings

- **Path Validation**: All paths validated against traversal attacks
- **Size Limits**: Files validated against size limits
- **Checksum Algorithm**: SHA-256 for integrity verification

## Monitoring & Logging

### Security Events

All backup operations are logged as security events:

- `BACKUP_CREATED`: Backup creation with file counts
- `BACKUP_RESTORED`: Backup restoration operations
- `BACKUP_DELETED`: Backup cleanup operations

### Performance Metrics

- Backup creation time
- File validation time
- Restoration time
- Storage space usage

### Debug Information

Comprehensive logging available for troubleshooting:

- Individual file backup status
- Checksum validation results
- Error details and stack traces
- Recovery operation outcomes

## Future Enhancements

### Planned Features

- **Incremental Backups**: Only backup changed files
- **Compression**: Reduce backup storage requirements
- **Remote Storage**: Support for cloud backup storage
- **Backup History**: Maintain multiple backup versions
- **Automatic Cleanup**: Configurable backup retention policies

### Configuration Options

- Backup retention time limits
- Maximum backup storage size
- Compression algorithms
- Remote storage providers

## Migration Guide

### From Legacy Code

```python
# Old way (no backup protection)
results = code_cleaner.clean_files(package_dir)

# New way (with backup protection)
result = code_cleaner.clean_files_with_backup(package_dir)
```

### API Changes

- `clean_files()` method preserved for compatibility
- New `clean_files_with_backup()` method added
- New `PackageCleaningResult` return type
- `BackupMetadata` includes all backup information

### Gradual Adoption

- Safe mode is enabled by default in new installations
- Legacy mode remains available for compatibility
- Existing scripts work without modification
- Enhanced error handling provides better user experience

______________________________________________________________________

This backup system transforms the code cleaner from a potentially risky operation into a completely safe one, ensuring that users can confidently clean their code without fear of data loss.
