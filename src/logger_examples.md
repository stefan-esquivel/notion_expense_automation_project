# Logger Usage Guide

## Overview

The modular logger (`src/logger.py`) provides a centralized, singleton logging system that can be used throughout the application.

## Basic Usage

### Import and Use

```python
from src.logger import get_logger

# Get logger for current module
logger = get_logger(__name__)

# Log messages
logger.info("Processing receipt...")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error!")
```

## Features

### 1. Singleton Pattern
- One logger instance shared across the entire application
- Consistent configuration everywhere
- No duplicate log entries

### 2. Dual Output
- **File logs**: Detailed logs with filename and line numbers
  - Location: `logs/expense_automation_YYYYMMDD.log`
  - Format: `2026-05-07 14:30:45 - expense_automation - INFO - [main.py:42] - Processing receipt...`
  
- **Console logs**: Simpler, cleaner output
  - Format: `14:30:45 - INFO - Processing receipt...`

### 3. Automatic Configuration
- Reads log folder from `Config.LOG_FOLDER`
- Creates log directory if it doesn't exist
- Daily log rotation (new file per day)

## Usage Examples

### In Workflow Nodes

```python
# src/workflows/langgraph/nodes/extract_node.py
from src.logger import get_logger

logger = get_logger(__name__)

def extract_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:
    logger.info("Starting extraction node")
    
    try:
        # ... extraction logic ...
        logger.debug(f"Extracted {len(items)} items")
        logger.info("Extraction complete")
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
    
    return state
```

### In Service Classes

```python
# src/pdf_extractor.py
from src.logger import get_logger

class PDFExtractor:
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def extract_text(self, pdf_path):
        self.logger.info(f"Extracting text from {pdf_path}")
        # ... extraction logic ...
```

### In Utility Functions

```python
# src/file_organizer.py
from src.logger import get_logger

logger = get_logger(__name__)

def organize_file(file_path, date, merchant):
    logger.info(f"Organizing file: {file_path.name}")
    # ... organization logic ...
    logger.info(f"File moved to: {new_path}")
```

## Log Levels

Use appropriate log levels:

- **DEBUG**: Detailed diagnostic information (not shown in console by default)
- **INFO**: General informational messages about program execution
- **WARNING**: Warning messages for potentially problematic situations
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical errors that may cause program termination

## Best Practices

1. **Use `__name__` for logger names**
   ```python
   logger = get_logger(__name__)
   ```
   This creates hierarchical loggers (e.g., `src.workflows.langgraph.nodes.extract_node`)

2. **Log at appropriate levels**
   - Use INFO for normal workflow steps
   - Use DEBUG for detailed diagnostic info
   - Use ERROR for exceptions with `exc_info=True`

3. **Include context in log messages**
   ```python
   logger.info(f"Processing receipt: {receipt_id}")
   logger.error(f"Failed to parse date from: {date_str}", exc_info=True)
   ```

4. **Use structured logging for errors**
   ```python
   try:
       # ... code ...
   except Exception as e:
       logger.error(f"Operation failed: {e}", exc_info=True)
   ```

## Testing

For testing, you can reset the logger:

```python
from src.logger import AppLogger

# In test teardown
AppLogger.reset()
```

## Migration from Old Logging

### Before (in main.py)
```python
def setup_logging():
    logging.basicConfig(...)
    return logging.getLogger(__name__)

class ExpenseAutomation:
    def __init__(self):
        self.logger = setup_logging()
```

### After (anywhere in the app)
```python
from src.logger import get_logger

logger = get_logger(__name__)

class ExpenseAutomation:
    def __init__(self):
        self.logger = get_logger(__name__)
```

## Configuration

The logger automatically uses settings from `Config`:
- `Config.LOG_FOLDER`: Directory for log files
- Log file naming: `expense_automation_YYYYMMDD.log`

No additional configuration needed!