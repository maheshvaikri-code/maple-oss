#!/usr/bin/env python3
"""
BROKER TEST FIX
Creator: Mahesh Vaikri

Fix the specific broker test issue.
"""
import sys
import os

# Add the project root to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

def test_broker_specifically():
    print("🔧 BROKER TEST DEBUG")
    print("=" * 30)
    
    try:
        print("1️⃣ Testing broker import...")
        from maple.broker.broker import MessageBroker
        from maple import Config, Message, Priority
        print("✅ Imports successful")
        
        print("2️⃣ Creating config...")
        config = Config(agent_id="test", broker_url="memory://test")
        print("✅ Config created")
        
        print("3️⃣ Creating broker...")
        broker = MessageBroker(config)
        print("✅ Broker created")
        
        print("4️⃣ Connecting broker...")
        broker.connect()
        print(f"✅ Broker connected, running: {broker.running}")
        assert broker.running == True
        
        print("5️⃣ Creating message...")
        msg = Message(
            message_type="TEST",
            receiver="test_receiver",
            sender="test_sender",
            priority=Priority.MEDIUM,
            payload={"test": "data"}
        )
        print("✅ Message created")
        
        print("6️⃣ Sending message...")
        message_id = broker.send(msg)
        print(f"✅ Message sent, ID: {message_id}")
        print(f"✅ Message ID type: {type(message_id)}")
        print(f"✅ Message ID length: {len(message_id) if message_id else 0}")
        
        assert isinstance(message_id, str), f"Expected string, got {type(message_id)}"
        assert len(message_id) > 0, "Message ID should not be empty"
        
        print("7️⃣ Checking queues...")
        print(f"✅ Agent queues: {list(broker._agent_queues.keys())}")
        assert "test_receiver" in broker._agent_queues
        
        print("8️⃣ Disconnecting...")
        broker.disconnect()
        print(f"✅ Broker disconnected, running: {broker.running}")
        
        print("\n🎉 ALL BROKER TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ BROKER TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_broker_specifically()
    if success:
        print("\n🔧 Now let's fix the main test...")
    sys.exit(0 if success else 1)
