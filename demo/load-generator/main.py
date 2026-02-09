# load-generator/main.py - Comprehensive Load Generator

import requests
import random
import time
import os
from datetime import datetime
from typing import Dict, List

TARGET_URL = os.getenv("TARGET_URL", "http://fastapi-app:8000")
REQUESTS_PER_SECOND = int(os.getenv("REQUESTS_PER_SECOND", "10"))
ERROR_SCENARIO = os.getenv("ERROR_SCENARIO", "all")  # all, db, network, code, timeout

# ============================================================================
# ENDPOINT CONFIGURATIONS
# ============================================================================

ALL_ENDPOINTS = {
    # Basic endpoints
    "health": {"path": "/", "method": "GET", "weight": 5},
    
    # Database errors
    "get_users": {"path": "/api/users", "method": "GET", "weight": 20},
    "create_user": {"path": "/api/users", "method": "POST", "weight": 15},
    "deadlock": {"path": "/api/deadlock", "method": "GET", "weight": 2},
    "slow_query": {"path": "/api/slow-query", "method": "GET", "weight": 5},
    
    # Network errors
    "external_api": {"path": "/api/external-api", "method": "GET", "weight": 10},
    
    # Memory errors
    "memory_leak": {"path": "/api/memory-leak", "method": "GET", "weight": 3},
    "oom": {"path": "/api/oom", "method": "GET", "weight": 1},
    
    # Code-level errors
    "null_pointer": {"path": "/api/null-pointer", "method": "GET", "weight": 5},
    "division_zero": {"path": "/api/division-by-zero", "method": "GET", "weight": 3},
    "index_error": {"path": "/api/index-out-of-bounds", "method": "GET", "weight": 3},
    "type_error": {"path": "/api/type-error", "method": "GET", "weight": 3},
    
    # HTTP errors
    "error_400": {"path": "/api/error/400", "method": "GET", "weight": 5},
    "error_401": {"path": "/api/error/401", "method": "GET", "weight": 2},
    "error_403": {"path": "/api/error/403", "method": "GET", "weight": 2},
    "error_404": {"path": "/api/error/404", "method": "GET", "weight": 3},
    "error_500": {"path": "/api/error/500", "method": "GET", "weight": 4},
    "error_502": {"path": "/api/error/502", "method": "GET", "weight": 2},
    "error_503": {"path": "/api/error/503", "method": "GET", "weight": 2},
    
    # Timeout errors
    "timeout": {"path": "/api/timeout", "method": "GET", "weight": 3},
    
    # Random errors
    "random": {"path": "/api/random", "method": "GET", "weight": 10},
}

# Error scenario filters
SCENARIOS = {
    "all": ALL_ENDPOINTS,
    "db": {k: v for k, v in ALL_ENDPOINTS.items() if k in ["get_users", "create_user", "deadlock", "slow_query"]},
    "network": {k: v for k, v in ALL_ENDPOINTS.items() if k in ["external_api"]},
    "code": {k: v for k, v in ALL_ENDPOINTS.items() if k in ["null_pointer", "division_zero", "index_error", "type_error"]},
    "timeout": {k: v for k, v in ALL_ENDPOINTS.items() if k in ["timeout", "slow_query"]},
    "memory": {k: v for k, v in ALL_ENDPOINTS.items() if k in ["memory_leak", "oom"]},
}

def weighted_choice(endpoints: Dict) -> Dict:
    """Select endpoint based on weights"""
    total_weight = sum(e["weight"] for e in endpoints.values())
    r = random.uniform(0, total_weight)
    cumulative = 0
    
    for name, endpoint in endpoints.items():
        cumulative += endpoint["weight"]
        if r <= cumulative:
            return endpoint
    
    return list(endpoints.values())[0]

def make_request(endpoint: Dict):
    """Make HTTP request to endpoint"""
    url = f"{TARGET_URL}{endpoint['path']}"
    method = endpoint['method']
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=12)
        elif method == "POST":
            # Generate random user data for POST /api/users
            if "/api/users" in endpoint['path']:
                username = f"user_{random.randint(1000, 9999)}_{int(time.time())}"
                email = f"{username}@example.com"
                response = requests.post(
                    url,
                    params={"username": username, "email": email},
                    timeout=12
                )
            else:
                response = requests.post(url, timeout=12)
        else:
            return
        
        # Log with emoji
        if 200 <= response.status_code < 300:
            emoji = "✅"
            color = "green"
        elif 400 <= response.status_code < 500:
            emoji = "⚠️ "
            color = "yellow"
        else:
            emoji = "❌"
            color = "red"
        
        print(f"{emoji} [{datetime.now().strftime('%H:%M:%S')}] {method:4s} {endpoint['path']:30s} → {response.status_code}")
        
    except requests.exceptions.Timeout:
        print(f"⏱️  [{datetime.now().strftime('%H:%M:%S')}] {method:4s} {endpoint['path']:30s} → TIMEOUT")
    except requests.exceptions.ConnectionError:
        print(f"🔌 [{datetime.now().strftime('%H:%M:%S')}] {method:4s} {endpoint['path']:30s} → CONNECTION ERROR")
    except Exception as e:
        print(f"💥 [{datetime.now().strftime('%H:%M:%S')}] {method:4s} {endpoint['path']:30s} → ERROR: {str(e)[:50]}")

def enable_error_simulations():
    """Enable all error simulations in the app"""
    try:
        # Enable DB failures
        requests.post(f"{TARGET_URL}/control/db-failures", params={"enable": True, "rate": 0.2})
        print("✓ Enabled database failure simulation (20%)")
        
        # Enable memory leak
        requests.post(f"{TARGET_URL}/control/memory-leak", params={"enable": True})
        print("✓ Enabled memory leak simulation")
        
    except:
        pass

def main():
    """Main load generator loop"""
    print("=" * 80)
    print("🚀 VizGenie Comprehensive Error Generator")
    print("=" * 80)
    print(f"📍 Target: {TARGET_URL}")
    print(f"⚡ Rate: {REQUESTS_PER_SECOND} requests/second")
    print(f"🎯 Scenario: {ERROR_SCENARIO}")
    print("=" * 80)
    
    # Wait for services
    print("\n⏳ Waiting for services to be ready...")
    time.sleep(10)
    
    # Enable error simulations
    print("\n⚙️  Configuring error simulations...")
    enable_error_simulations()
    
    # Select scenario
    endpoints = SCENARIOS.get(ERROR_SCENARIO, ALL_ENDPOINTS)
    
    print(f"\n📋 Active endpoints: {len(endpoints)}")
    for name, endpoint in list(endpoints.items())[:5]:
        print(f"   - {name}: {endpoint['path']}")
    if len(endpoints) > 5:
        print(f"   ... and {len(endpoints) - 5} more")
    
    print("\n" + "=" * 80)
    print("Starting load generation (Press Ctrl+C to stop)")
    print("=" * 80 + "\n")
    
    delay = 1.0 / REQUESTS_PER_SECOND
    request_count = 0
    error_count = 0
    
    while True:
        try:
            endpoint = weighted_choice(endpoints)
            make_request(endpoint)
            request_count += 1
            
            # Print summary every 100 requests
            if request_count % 100 == 0:
                print(f"\n📊 Progress: {request_count} requests sent\n")
            
            time.sleep(delay)
            
        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print(f"🛑 Load generator stopped")
            print(f"📊 Total requests: {request_count}")
            print(f"{'='*80}\n")
            break
        except Exception as e:
            print(f"💥 Unexpected error: {str(e)}")
            time.sleep(1)

if __name__ == "__main__":
    main()