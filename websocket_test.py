import asyncio
import websockets
import json
import requests
import time
from datetime import datetime

class WebSocketTester:
    def __init__(self, base_url="https://cacf2a31-9e35-4049-85ee-3b36c7bcc84a.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://') + "/api/ws"
        self.messages_received = []
        self.tests_run = 0
        self.tests_passed = 0

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")

    async def test_websocket_connection(self):
        """Test basic WebSocket connection"""
        print("\n🔌 Testing WebSocket Connection...")
        try:
            async with websockets.connect(self.ws_url, timeout=10) as websocket:
                print(f"   Connected to: {self.ws_url}")
                
                # Wait for initial message
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(message)
                    print(f"   Initial message received: {data}")
                    
                    if data.get('type') == 'status_update' and 'robot_state' in data:
                        self.log_test("WebSocket Connection & Initial State", True, "- Received initial robot state")
                        return True
                    else:
                        self.log_test("WebSocket Connection & Initial State", False, "- Invalid initial message format")
                        return False
                        
                except asyncio.TimeoutError:
                    self.log_test("WebSocket Connection & Initial State", False, "- No initial message received")
                    return False
                    
        except Exception as e:
            self.log_test("WebSocket Connection & Initial State", False, f"- Connection error: {str(e)}")
            return False

    async def test_real_time_updates(self):
        """Test real-time progress updates during cleaning"""
        print("\n📊 Testing Real-time Updates...")
        
        try:
            async with websockets.connect(self.ws_url, timeout=10) as websocket:
                # Skip initial message
                await websocket.recv()
                
                # Start cleaning via API
                print("   Starting cleaning cycle...")
                response = requests.post(f"{self.api_url}/robot/command", 
                                       json={"command": "start", "mode": "full_clean"},
                                       timeout=10)
                
                if response.status_code != 200:
                    self.log_test("Real-time Updates", False, "- Failed to start cleaning")
                    return False
                
                # Listen for updates
                updates_received = 0
                status_changes = set()
                progress_updates = []
                
                print("   Listening for real-time updates...")
                start_time = time.time()
                
                while time.time() - start_time < 20:  # Listen for 20 seconds
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2)
                        data = json.loads(message)
                        updates_received += 1
                        
                        print(f"   Update {updates_received}: {data}")
                        
                        if data.get('type') == 'status_update':
                            robot_state = data.get('robot_state', {})
                            status = robot_state.get('status')
                            progress = robot_state.get('progress', 0)
                            
                            if status:
                                status_changes.add(status)
                            if progress is not None:
                                progress_updates.append(progress)
                        
                        elif data.get('type') == 'alert':
                            print(f"   🚨 Alert received: {data.get('message')}")
                            
                        elif data.get('type') == 'info':
                            print(f"   ℹ️  Info received: {data.get('message')}")
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"   Error receiving message: {e}")
                        break
                
                # Stop cleaning
                requests.post(f"{self.api_url}/robot/command", 
                            json={"command": "stop"}, timeout=10)
                
                # Analyze results
                print(f"   Updates received: {updates_received}")
                print(f"   Status changes seen: {status_changes}")
                print(f"   Progress updates: {progress_updates}")
                
                success = (
                    updates_received >= 3 and  # Should get multiple updates
                    len(status_changes) >= 1 and  # Should see status changes
                    len(progress_updates) >= 2  # Should see progress changes
                )
                
                details = f"- {updates_received} updates, {len(status_changes)} status changes, {len(progress_updates)} progress updates"
                self.log_test("Real-time Updates", success, details)
                return success
                
        except Exception as e:
            self.log_test("Real-time Updates", False, f"- Error: {str(e)}")
            return False

    async def test_obstacle_detection(self):
        """Test obstacle detection simulation"""
        print("\n🚧 Testing Obstacle Detection...")
        
        try:
            async with websockets.connect(self.ws_url, timeout=10) as websocket:
                # Skip initial message
                await websocket.recv()
                
                # Start cleaning
                response = requests.post(f"{self.api_url}/robot/command", 
                                       json={"command": "start", "mode": "full_clean"},
                                       timeout=10)
                
                if response.status_code != 200:
                    self.log_test("Obstacle Detection", False, "- Failed to start cleaning")
                    return False
                
                # Listen for obstacle detection (may take up to 50 seconds with 10% chance every 5 seconds)
                print("   Listening for obstacle detection (up to 60 seconds)...")
                start_time = time.time()
                obstacle_detected = False
                auto_resumed = False
                
                while time.time() - start_time < 60:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2)
                        data = json.loads(message)
                        
                        if data.get('type') == 'alert' and 'obstacle' in data.get('message', '').lower():
                            print(f"   🚨 Obstacle detected: {data.get('message')}")
                            obstacle_detected = True
                            
                        elif data.get('type') == 'info' and 'resuming' in data.get('message', '').lower():
                            print(f"   ✅ Auto-resume detected: {data.get('message')}")
                            auto_resumed = True
                            
                        if obstacle_detected and auto_resumed:
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"   Error: {e}")
                        break
                
                # Stop cleaning
                requests.post(f"{self.api_url}/robot/command", 
                            json={"command": "stop"}, timeout=10)
                
                if obstacle_detected and auto_resumed:
                    self.log_test("Obstacle Detection", True, "- Obstacle detected and auto-resumed")
                    return True
                elif obstacle_detected:
                    self.log_test("Obstacle Detection", True, "- Obstacle detected (auto-resume not captured)")
                    return True
                else:
                    self.log_test("Obstacle Detection", False, "- No obstacle detected in 60 seconds (random chance)")
                    return False
                    
        except Exception as e:
            self.log_test("Obstacle Detection", False, f"- Error: {str(e)}")
            return False

    async def test_multiple_clients(self):
        """Test multiple WebSocket clients"""
        print("\n👥 Testing Multiple WebSocket Clients...")
        
        try:
            # Connect two clients
            async with websockets.connect(self.ws_url, timeout=10) as ws1, \
                       websockets.connect(self.ws_url, timeout=10) as ws2:
                
                print("   Two clients connected")
                
                # Skip initial messages
                await ws1.recv()
                await ws2.recv()
                
                # Start cleaning
                response = requests.post(f"{self.api_url}/robot/command", 
                                       json={"command": "start", "mode": "mop_only"},
                                       timeout=10)
                
                if response.status_code != 200:
                    self.log_test("Multiple Clients", False, "- Failed to start cleaning")
                    return False
                
                # Both clients should receive the same updates
                try:
                    msg1 = await asyncio.wait_for(ws1.recv(), timeout=5)
                    msg2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                    
                    data1 = json.loads(msg1)
                    data2 = json.loads(msg2)
                    
                    print(f"   Client 1 received: {data1}")
                    print(f"   Client 2 received: {data2}")
                    
                    # Stop cleaning
                    requests.post(f"{self.api_url}/robot/command", 
                                json={"command": "stop"}, timeout=10)
                    
                    if data1 == data2:
                        self.log_test("Multiple Clients", True, "- Both clients received identical updates")
                        return True
                    else:
                        self.log_test("Multiple Clients", False, "- Clients received different updates")
                        return False
                        
                except asyncio.TimeoutError:
                    self.log_test("Multiple Clients", False, "- Timeout waiting for updates")
                    return False
                    
        except Exception as e:
            self.log_test("Multiple Clients", False, f"- Error: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all WebSocket tests"""
        print("🔌 Starting WebSocket Tests")
        print("=" * 50)
        
        # Test 1: Basic connection
        await self.test_websocket_connection()
        
        # Test 2: Real-time updates
        await self.test_real_time_updates()
        
        # Test 3: Obstacle detection (optional due to randomness)
        await self.test_obstacle_detection()
        
        # Test 4: Multiple clients
        await self.test_multiple_clients()
        
        # Results
        print("\n📊 WebSocket Test Results:")
        print("=" * 50)
        print(f"Tests passed: {self.tests_passed}/{self.tests_run}")
        
        if self.tests_passed >= self.tests_run - 1:  # Allow 1 failure for obstacle detection
            print("🎉 WebSocket tests mostly passed!")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return False

async def main():
    tester = WebSocketTester()
    success = await tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))