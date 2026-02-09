# app/main.py - Comprehensive Error Generation

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import logging
import json
import time
import random
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# ============================================================================
# STRUCTURED LOGGING SETUP
# ============================================================================

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'http_status'):
            log_data['http_status'] = record.http_status
        if hasattr(record, 'http_method'):
            log_data['http_method'] = record.http_method
        if hasattr(record, 'path'):
            log_data['path'] = record.path
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'error_type'):
            log_data['error_type'] = record.error_type
        if hasattr(record, 'error_code'):
            log_data['error_code'] = record.error_code
        if hasattr(record, 'stack_trace'):
            log_data['stack_trace'] = record.stack_trace
            
        return json.dumps(log_data)

logger = logging.getLogger("fastapi-app")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'HTTP requests in progress'
)

error_counter = Counter(
    'application_errors_total',
    'Total application errors',
    ['error_type', 'endpoint']
)

db_connections_total = Counter(
    'database_connections_total',
    'Total database connections',
    ['status']
)

memory_usage_bytes = Gauge(
    'memory_usage_bytes',
    'Application memory usage'
)

cpu_usage_percent = Gauge(
    'cpu_usage_percent',
    'Application CPU usage percentage'
)

# ============================================================================
# APPLICATION SETUP
# ============================================================================

app = FastAPI(title="VizGenie Error Generation Demo")

# Global state for error simulation
class ErrorSimulator:
    """Manages different error scenarios"""
    
    def __init__(self):
        self.db_connection_failure_rate = 0.0
        self.memory_leak_active = False
        self.cpu_spike_active = False
        self.network_failure_active = False
        self.deadlock_active = False
        self.cache = {}  # Simulated cache for memory leak
        
    def toggle_db_failures(self, rate: float = 0.3):
        """Toggle database connection failures"""
        self.db_connection_failure_rate = rate
        logger.warning(f"Database failure simulation: {rate*100}% failure rate")
    
    def toggle_memory_leak(self, active: bool = True):
        """Toggle memory leak simulation"""
        self.memory_leak_active = active
        logger.warning(f"Memory leak simulation: {'ACTIVE' if active else 'INACTIVE'}")
    
    def trigger_oom(self):
        """Trigger out-of-memory error"""
        logger.critical("Triggering OutOfMemory error simulation")
        try:
            # Simulate memory exhaustion
            large_data = [0] * (10**8)  # Large allocation
            raise MemoryError("Cannot allocate memory: heap exhausted")
        except MemoryError as e:
            logger.error(str(e), extra={'error_type': 'OutOfMemory'})
            raise HTTPException(status_code=503, detail="Service temporarily unavailable - memory exhausted")

error_sim = ErrorSimulator()

# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db_connection():
    """Get database connection with simulated failures"""
    
    # Simulate connection failures
    if random.random() < error_sim.db_connection_failure_rate:
        db_connections_total.labels(status='failure').inc()
        error_counter.labels(error_type='DatabaseConnectionError', endpoint='global').inc()
        
        error_msg = random.choice([
            "could not connect to server: Connection refused",
            "FATAL: remaining connection slots are reserved",
            "timeout: connection pool exhausted",
            "psycopg2.OperationalError: server closed the connection unexpectedly",
            "connection to server was lost"
        ])
        
        logger.error(
            f"Database connection failed: {error_msg}",
            extra={'error_type': 'DatabaseConnectionError', 'error_code': 'DB_CONN_001'}
        )
        raise Exception(error_msg)
    
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL", "postgresql://postgres:admin@postgres:5432/app_db"),
            connect_timeout=5
        )
        db_connections_total.labels(status='success').inc()
        return conn
    except psycopg2.OperationalError as e:
        db_connections_total.labels(status='failure').inc()
        error_counter.labels(error_type='DatabaseConnectionError', endpoint='global').inc()
        logger.error(
            f"Database connection failed: {str(e)}",
            extra={'error_type': 'DatabaseConnectionError', 'error_code': 'DB_CONN_002'}
        )
        raise
    except Exception as e:
        db_connections_total.labels(status='failure').inc()
        logger.error(f"Unexpected database error: {str(e)}", extra={'error_type': 'UnexpectedDatabaseError'})
        raise

# ============================================================================
# MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Metrics and logging middleware"""
    http_requests_in_progress.inc()
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # Log request
        log_level = logging.ERROR if response.status_code >= 500 else \
                   logging.WARNING if response.status_code >= 400 else \
                   logging.INFO
        
        logger.log(
            log_level,
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                'http_method': request.method,
                'path': request.url.path,
                'http_status': response.status_code,
                'duration_ms': round(duration * 1000, 2)
            }
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        
        # Log exception
        import traceback
        stack_trace = traceback.format_exc()
        
        error_counter.labels(
            error_type=type(e).__name__,
            endpoint=request.url.path
        ).inc()
        
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                'http_method': request.method,
                'path': request.url.path,
                'error_type': type(e).__name__,
                'duration_ms': round(duration * 1000, 2),
                'stack_trace': stack_trace
            }
        )
        raise
    finally:
        http_requests_in_progress.dec()

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                product_name VARCHAR(100) NOT NULL,
                quantity INTEGER NOT NULL,
                locked_by INTEGER REFERENCES users(id),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(
            f"Failed to initialize database: {str(e)}",
            extra={'error_type': 'DatabaseInitError', 'error_code': 'DB_INIT_001'}
        )

# ============================================================================
# BASIC ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    logger.info("Root endpoint accessed")
    return {"status": "healthy", "service": "VizGenie Error Demo"}

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ============================================================================
# ERROR TYPE 1: DATABASE ERRORS
# ============================================================================

@app.get("/api/users")
async def get_users():
    """Get users - may fail with DB connection error"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        logger.info(f"Retrieved {len(users)} users")
        return {"users": users, "count": len(users)}
        
    except Exception as e:
        error_counter.labels(error_type='DatabaseQueryError', endpoint='/api/users').inc()
        logger.error(
            f"Failed to retrieve users: {str(e)}",
            extra={'error_type': 'DatabaseQueryError', 'error_code': 'DB_QUERY_001'}
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/users")
async def create_user(username: str, email: str):
    """Create user - validation, duplicate, and DB errors"""
    
    # Validation error (10%)
    if random.random() < 0.1:
        error_counter.labels(error_type='ValidationError', endpoint='/api/users').inc()
        logger.warning(
            f"User creation failed - validation error: {username}",
            extra={'error_type': 'ValidationError', 'error_code': 'VAL_001'}
        )
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
            (username, email)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"User created successfully: {username}")
        return {"id": user_id, "username": username, "email": email}
        
    except psycopg2.IntegrityError as e:
        error_counter.labels(error_type='DuplicateError', endpoint='/api/users').inc()
        logger.warning(
            f"Duplicate user creation attempt: {username}",
            extra={'error_type': 'DuplicateError', 'error_code': 'DB_DUP_001'}
        )
        raise HTTPException(status_code=409, detail="User already exists")
        
    except Exception as e:
        error_counter.labels(error_type='DatabaseError', endpoint='/api/users').inc()
        logger.error(
            f"User creation failed: {str(e)}",
            extra={'error_type': 'DatabaseError', 'error_code': 'DB_ERR_001'}
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/deadlock")
async def trigger_deadlock():
    """Trigger database deadlock"""
    try:
        conn1 = get_db_connection()
        conn2 = get_db_connection()
        
        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()
        
        # Start transactions
        cursor1.execute("BEGIN")
        cursor2.execute("BEGIN")
        
        # Lock resources in different order
        cursor1.execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = 1")
        time.sleep(0.1)
        cursor2.execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = 2")
        time.sleep(0.1)
        
        # Try to access each other's locked resources (deadlock!)
        cursor1.execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = 2")
        cursor2.execute("UPDATE inventory SET quantity = quantity - 1 WHERE id = 1")
        
        conn1.commit()
        conn2.commit()
        
        cursor1.close()
        cursor2.close()
        conn1.close()
        conn2.close()
        
        return {"status": "completed"}
        
    except psycopg2.extensions.TransactionRollbackError as e:
        error_counter.labels(error_type='DatabaseDeadlock', endpoint='/api/deadlock').inc()
        logger.error(
            f"Deadlock detected: {str(e)}",
            extra={'error_type': 'DatabaseDeadlock', 'error_code': 'DB_DEADLOCK_001'}
        )
        raise HTTPException(status_code=500, detail="Database deadlock occurred")
        
    except Exception as e:
        error_counter.labels(error_type='DatabaseError', endpoint='/api/deadlock').inc()
        logger.error(f"Deadlock simulation failed: {str(e)}", extra={'error_type': 'DatabaseError'})
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# ERROR TYPE 2: TIMEOUT ERRORS
# ============================================================================

@app.get("/api/slow-query")
async def slow_query():
    """Slow database query"""
    start = time.time()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Slow query
        time.sleep(random.uniform(3.0, 5.0))
        cursor.execute("SELECT * FROM users LIMIT 10")
        users = cursor.fetchall()
        
        duration = (time.time() - start) * 1000
        
        logger.warning(
            f"Slow query completed in {duration:.2f}ms",
            extra={'error_type': 'SlowQuery', 'duration_ms': duration, 'error_code': 'PERF_001'}
        )
        
        cursor.close()
        conn.close()
        
        return {"users": users, "duration_ms": duration}
        
    except Exception as e:
        error_counter.labels(error_type='QueryTimeout', endpoint='/api/slow-query').inc()
        logger.error(
            f"Query timeout: {str(e)}",
            extra={'error_type': 'QueryTimeout', 'error_code': 'DB_TIMEOUT_001'}
        )
        raise HTTPException(status_code=504, detail="Gateway timeout")

@app.get("/api/timeout")
async def timeout_endpoint():
    """Request timeout simulation"""
    delay = random.uniform(5.0, 10.0)
    
    logger.warning(
        f"Timeout endpoint - sleeping {delay:.2f}s",
        extra={'error_type': 'RequestTimeout', 'delay_seconds': delay}
    )
    
    time.sleep(delay)
    
    return {"status": "completed", "delay": delay}

# ============================================================================
# ERROR TYPE 3: NETWORK ERRORS
# ============================================================================

@app.get("/api/external-api")
async def call_external_api():
    """Call external API - network errors"""
    import requests
    
    # Simulate network failures
    if random.random() < 0.3:
        error_type = random.choice([
            "ConnectionError",
            "ConnectionResetError",
            "BrokenPipeError",
            "DNSError"
        ])
        
        error_counter.labels(error_type=error_type, endpoint='/api/external-api').inc()
        
        error_messages = {
            "ConnectionError": "connection refused by remote host",
            "ConnectionResetError": "connection reset by peer",
            "BrokenPipeError": "broken pipe: write failed",
            "DNSError": "DNS resolution failed: name not resolved"
        }
        
        logger.error(
            f"External API call failed: {error_messages[error_type]}",
            extra={'error_type': error_type, 'error_code': 'NET_001'}
        )
        
        raise HTTPException(status_code=503, detail=error_messages[error_type])
    
    try:
        # Simulate successful call
        response = requests.get("https://jsonplaceholder.typicode.com/posts/1", timeout=2)
        return response.json()
        
    except requests.exceptions.Timeout:
        error_counter.labels(error_type='NetworkTimeout', endpoint='/api/external-api').inc()
        logger.error(
            "External API timeout",
            extra={'error_type': 'NetworkTimeout', 'error_code': 'NET_TIMEOUT_001'}
        )
        raise HTTPException(status_code=504, detail="External service timeout")
        
    except Exception as e:
        error_counter.labels(error_type='NetworkError', endpoint='/api/external-api').inc()
        logger.error(
            f"External API error: {str(e)}",
            extra={'error_type': 'NetworkError', 'error_code': 'NET_ERR_001'}
        )
        raise HTTPException(status_code=503, detail="Service unavailable")

# ============================================================================
# ERROR TYPE 4: MEMORY ERRORS
# ============================================================================

@app.get("/api/memory-leak")
async def memory_leak():
    """Simulate memory leak"""
    
    if error_sim.memory_leak_active:
        # Add to cache (memory leak)
        key = f"leak_{len(error_sim.cache)}"
        error_sim.cache[key] = [0] * (10**6)  # 1M integers
        
        logger.warning(
            f"Memory leak: cache size = {len(error_sim.cache)}",
            extra={'error_type': 'MemoryLeak', 'cache_size': len(error_sim.cache)}
        )
    
    return {"cache_size": len(error_sim.cache), "leak_active": error_sim.memory_leak_active}

@app.get("/api/oom")
async def trigger_oom():
    """Trigger out-of-memory error"""
    error_sim.trigger_oom()

# ============================================================================
# ERROR TYPE 5: CODE-LEVEL ERRORS
# ============================================================================

@app.get("/api/null-pointer")
async def null_pointer_error():
    """Simulate null pointer / AttributeError"""
    try:
        obj = None
        result = obj.some_method()  # AttributeError
        return {"result": result}
        
    except AttributeError as e:
        error_counter.labels(error_type='NullPointerError', endpoint='/api/null-pointer').inc()
        
        import traceback
        stack_trace = traceback.format_exc()
        
        logger.error(
            f"NullPointerError: {str(e)}",
            extra={
                'error_type': 'NullPointerError',
                'error_code': 'CODE_NULL_001',
                'stack_trace': stack_trace
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/division-by-zero")
async def division_by_zero():
    """Simulate division by zero error"""
    try:
        x = random.randint(1, 100)
        y = 0
        result = x / y  # ZeroDivisionError
        return {"result": result}
        
    except ZeroDivisionError as e:
        error_counter.labels(error_type='DivisionByZero', endpoint='/api/division-by-zero').inc()
        
        import traceback
        stack_trace = traceback.format_exc()
        
        logger.error(
            f"Division by zero: {str(e)}",
            extra={
                'error_type': 'DivisionByZero',
                'error_code': 'CODE_MATH_001',
                'stack_trace': stack_trace
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/index-out-of-bounds")
async def index_error():
    """Simulate index out of bounds error"""
    try:
        arr = [1, 2, 3]
        value = arr[10]  # IndexError
        return {"value": value}
        
    except IndexError as e:
        error_counter.labels(error_type='IndexOutOfBounds', endpoint='/api/index-out-of-bounds').inc()
        
        import traceback
        stack_trace = traceback.format_exc()
        
        logger.error(
            f"Index out of bounds: {str(e)}",
            extra={
                'error_type': 'IndexOutOfBounds',
                'error_code': 'CODE_INDEX_001',
                'stack_trace': stack_trace
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/type-error")
async def type_error():
    """Simulate type error"""
    try:
        result = "string" + 123  # TypeError
        return {"result": result}
        
    except TypeError as e:
        error_counter.labels(error_type='TypeError', endpoint='/api/type-error').inc()
        
        import traceback
        stack_trace = traceback.format_exc()
        
        logger.error(
            f"Type error: {str(e)}",
            extra={
                'error_type': 'TypeError',
                'error_code': 'CODE_TYPE_001',
                'stack_trace': stack_trace
            }
        )
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# ERROR TYPE 6: HTTP ERRORS
# ============================================================================

@app.get("/api/error/400")
async def error_400():
    """Bad request"""
    error_counter.labels(error_type='BadRequest', endpoint='/api/error/400').inc()
    logger.warning("Bad request triggered", extra={'error_type': 'BadRequest', 'error_code': 'HTTP_400'})
    raise HTTPException(status_code=400, detail="Bad request")

@app.get("/api/error/401")
async def error_401():
    """Unauthorized"""
    error_counter.labels(error_type='Unauthorized', endpoint='/api/error/401').inc()
    logger.warning("Unauthorized access attempt", extra={'error_type': 'Unauthorized', 'error_code': 'HTTP_401'})
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/error/403")
async def error_403():
    """Forbidden"""
    error_counter.labels(error_type='Forbidden', endpoint='/api/error/403').inc()
    logger.warning("Forbidden access attempt", extra={'error_type': 'Forbidden', 'error_code': 'HTTP_403'})
    raise HTTPException(status_code=403, detail="Forbidden")

@app.get("/api/error/404")
async def error_404():
    """Not found"""
    error_counter.labels(error_type='NotFound', endpoint='/api/error/404').inc()
    logger.warning("Resource not found", extra={'error_type': 'NotFound', 'error_code': 'HTTP_404'})
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/api/error/500")
async def error_500():
    """Internal server error"""
    error_counter.labels(error_type='InternalServerError', endpoint='/api/error/500').inc()
    logger.error("Internal server error triggered", extra={'error_type': 'InternalServerError', 'error_code': 'HTTP_500'})
    raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/error/502")
async def error_502():
    """Bad gateway"""
    error_counter.labels(error_type='BadGateway', endpoint='/api/error/502').inc()
    logger.error("Bad gateway error", extra={'error_type': 'BadGateway', 'error_code': 'HTTP_502'})
    raise HTTPException(status_code=502, detail="Bad gateway")

@app.get("/api/error/503")
async def error_503():
    """Service unavailable"""
    error_counter.labels(error_type='ServiceUnavailable', endpoint='/api/error/503').inc()
    logger.error("Service unavailable", extra={'error_type': 'ServiceUnavailable', 'error_code': 'HTTP_503'})
    raise HTTPException(status_code=503, detail="Service unavailable")

# ============================================================================
# ERROR CONTROL ENDPOINTS
# ============================================================================

@app.post("/control/db-failures")
async def control_db_failures(enable: bool = True, rate: float = 0.3):
    """Enable/disable database failure simulation"""
    error_sim.toggle_db_failures(rate if enable else 0.0)
    return {"status": "updated", "enabled": enable, "rate": rate}

@app.post("/control/memory-leak")
async def control_memory_leak(enable: bool = True):
    """Enable/disable memory leak simulation"""
    error_sim.toggle_memory_leak(enable)
    return {"status": "updated", "enabled": enable}

@app.post("/control/clear-cache")
async def clear_cache():
    """Clear simulated cache"""
    size = len(error_sim.cache)
    error_sim.cache.clear()
    logger.info(f"Cache cleared: {size} items removed")
    return {"status": "cleared", "items_removed": size}

# ============================================================================
# RANDOM ERROR GENERATOR
# ============================================================================

@app.get("/api/random")
async def random_error():
    """Random error generator"""
    rand = random.random()
    
    if rand < 0.6:  # 60% success
        logger.info("Random endpoint - success")
        return {"status": "success", "data": {"value": random.randint(1, 100)}}
    elif rand < 0.7:  # 10% bad request
        error_counter.labels(error_type='BadRequest', endpoint='/api/random').inc()
        logger.warning("Random endpoint - bad request", extra={'error_type': 'BadRequest'})
        raise HTTPException(status_code=400, detail="Random bad request")
    elif rand < 0.85:  # 15% server error
        error_counter.labels(error_type='ServerError', endpoint='/api/random').inc()
        logger.error("Random endpoint - server error", extra={'error_type': 'ServerError'})
        raise HTTPException(status_code=500, detail="Random server error")
    else:  # 15% timeout
        error_counter.labels(error_type='Timeout', endpoint='/api/random').inc()
        logger.error("Random endpoint - timeout", extra={'error_type': 'Timeout'})
        time.sleep(6)
        raise HTTPException(status_code=504, detail="Request timeout")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)