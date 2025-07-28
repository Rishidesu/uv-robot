import requests
import sys
import time
import json
from datetime import datetime

class RobotAPITester:
    def __init__(self, base_url="https://cacf2a31-9e35-4049-85ee-3b36c7bcc84a.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else f"{self.api_url}/"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)}")
                    return True, response_data
                except:
                    print(f"   Response: {response.text}")
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        return self.run_test("Health Check", "GET", "", 200)

    def test_robot_status(self):
        """Test getting robot status"""
        return self.run_test("Get Robot Status", "GET", "robot/status", 200)

    def test_start_cleaning(self, mode="full_clean"):
        """Test starting cleaning cycle"""
        return self.run_test(
            f"Start Cleaning ({mode})",
            "POST",
            "robot/command",
            200,
            data={"command": "start", "mode": mode}
        )

    def test_pause_cleaning(self):
        """Test pausing cleaning cycle"""
        return self.run_test(
            "Pause Cleaning",
            "POST", 
            "robot/command",
            200,
            data={"command": "pause"}
        )

    def test_resume_cleaning(self):
        """Test resuming cleaning cycle"""
        return self.run_test(
            "Resume Cleaning",
            "POST",
            "robot/command", 
            200,
            data={"command": "resume"}
        )

    def test_stop_cleaning(self):
        """Test stopping cleaning cycle"""
        return self.run_test(
            "Stop Cleaning",
            "POST",
            "robot/command",
            200,
            data={"command": "stop"}
        )

    def test_cleaning_logs(self):
        """Test getting cleaning logs"""
        return self.run_test("Get Cleaning Logs", "GET", "cleaning-logs", 200)

    def test_invalid_command(self):
        """Test invalid robot command"""
        return self.run_test(
            "Invalid Command",
            "POST",
            "robot/command",
            422,  # FastAPI validation error
            data={"command": "invalid_command"}
        )

def main():
    print("🤖 Starting Robot Control API Tests")
    print("=" * 50)
    
    tester = RobotAPITester()
    
    # Test 1: Health check
    success, _ = tester.test_health_check()
    if not success:
        print("❌ Health check failed, stopping tests")
        return 1

    # Test 2: Get initial robot status
    success, initial_status = tester.test_robot_status()
    if success:
        print(f"   Initial robot state: {initial_status.get('robot_state', {}).get('status', 'unknown')}")

    # Test 3: Get cleaning logs (should work even if empty)
    tester.test_cleaning_logs()

    # Test 4: Start cleaning cycle
    success, start_response = tester.test_start_cleaning("full_clean")
    if success:
        print("   Cleaning started successfully")
        
        # Wait a bit for the robot to start
        print("   Waiting 3 seconds for robot to start...")
        time.sleep(3)
        
        # Test 5: Check status during cleaning
        success, status_response = tester.test_robot_status()
        if success:
            robot_state = status_response.get('robot_state', {})
            print(f"   Robot status during cleaning: {robot_state.get('status')}")
            print(f"   Progress: {robot_state.get('progress')}%")
            print(f"   Is cleaning: {robot_state.get('is_cleaning')}")

        # Test 6: Pause cleaning
        success, _ = tester.test_pause_cleaning()
        if success:
            time.sleep(1)
            
            # Test 7: Resume cleaning
            success, _ = tester.test_resume_cleaning()
            if success:
                time.sleep(1)
                
                # Test 8: Stop cleaning
                tester.test_stop_cleaning()

    # Test 9: Try different cleaning modes
    print("\n🔄 Testing different cleaning modes...")
    for mode in ["mop_only", "spray_only", "uv_only"]:
        success, _ = tester.test_start_cleaning(mode)
        if success:
            time.sleep(1)
            tester.test_stop_cleaning()
            time.sleep(1)

    # Test 10: Test invalid command
    tester.test_invalid_command()

    # Test 11: Test edge cases
    print("\n🧪 Testing edge cases...")
    
    # Try to pause when not cleaning
    print("\n🔍 Testing pause when not cleaning...")
    success, response = tester.run_test(
        "Pause When Not Cleaning",
        "POST",
        "robot/command",
        200,
        data={"command": "pause"}
    )
    if success and not response.get('success', True):
        print("   ✅ Correctly rejected pause when not cleaning")
    
    # Try to resume when not paused
    print("\n🔍 Testing resume when not paused...")
    success, response = tester.run_test(
        "Resume When Not Paused", 
        "POST",
        "robot/command",
        200,
        data={"command": "resume"}
    )
    if success and not response.get('success', True):
        print("   ✅ Correctly rejected resume when not paused")

    # Final status check
    print("\n📊 Final Results:")
    print("=" * 50)
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())