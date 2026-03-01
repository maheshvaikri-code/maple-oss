#!/usr/bin/env python3
"""
MAPLE LAUNCH COMMAND CENTER
Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

Your mission control for launching MAPLE to the world!
This script helps you execute the perfect launch sequence.

MAPLE - Multi Agent Protocol Language Engine
A multi-agent communication protocol.
"""

import os
import sys
import json
import webbrowser
from datetime import datetime
import subprocess

def print_mission_banner():
    """Print the launch mission banner."""
    banner = """
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀
🚀                                                                    🚀
🚀  ███╗   ███╗ █████╗ ██████╗ ██╗     ███████╗                    🚀
🚀  ████╗ ████║██╔══██╗██╔══██╗██║     ██╔════╝                    🚀
🚀  ██╔████╔██║███████║██████╔╝██║     █████╗                      🚀
🚀  ██║╚██╔╝██║██╔══██║██╔═══╝ ██║     ██╔══╝                      🚀
🚀  ██║ ╚═╝ ██║██║  ██║██║     ███████╗███████╗                    🚀
🚀  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝                    🚀
🚀                                                                    🚀
🚀             🎯 LAUNCH COMMAND CENTER 🎯                           🚀
🚀                                                                    🚀
🚀    Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)  🚀
🚀                                                                    🚀
🚀         🌟 READY TO CHANGE THE WORLD! 🌟                         🚀
🚀                                                                    🚀
🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀
    """
    print(banner)

def check_launch_readiness():
    """Check if MAPLE is ready for launch."""
    print("🔍 LAUNCH READINESS CHECK")
    print("=" * 50)
    
    checks = []
    
    # Check 1: MAPLE Installation
    try:
        import maple
        checks.append(("✅", "MAPLE installed and importable"))
    except ImportError:
        checks.append(("❌", "MAPLE not found - run 'pip install -e .'"))
    
    # Check 2: Demo files exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    killer_demo_path = os.path.join(script_dir, "killer_demo.py")
    
    if os.path.exists(killer_demo_path):
        checks.append(("✅", "Killer demo ready"))
    else:
        checks.append(("❌", "Killer demo missing"))
    
    # Check 3: Launch package
    launch_package_path = os.path.join(script_dir, "LAUNCH_PACKAGE.md")
    if os.path.exists(launch_package_path):
        checks.append(("✅", "Launch package ready"))
    else:
        checks.append(("❌", "Launch package missing"))
    
    # Check 4: GitHub repo status
    project_root = os.path.dirname(script_dir)
    if os.path.exists(os.path.join(project_root, ".git")):
        checks.append(("✅", "Git repository detected"))
    else:
        checks.append(("⚠️", "No git repository - consider version control"))
    
    # Check 5: README quality
    readme_path = os.path.join(project_root, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
        if len(readme_content) > 5000:
            checks.append(("✅", "High-quality README detected"))
        else:
            checks.append(("⚠️", "README could be more comprehensive"))
    else:
        checks.append(("❌", "README missing"))
    
    # Print results
    for status, message in checks:
        print(f"   {status} {message}")
    
    print()
    
    # Calculate readiness score
    success_count = sum(1 for status, _ in checks if status == "✅")
    total_checks = len(checks)
    readiness_score = (success_count / total_checks) * 100
    
    print(f"🎯 LAUNCH READINESS: {readiness_score:.0f}%")
    
    if readiness_score >= 80:
        print("🚀 READY FOR LAUNCH!")
        return True
    elif readiness_score >= 60:
        print("⚠️ MOSTLY READY - Address issues above")
        return False
    else:
        print("❌ NOT READY - Critical issues need fixing")
        return False

def run_killer_demo():
    """Run the killer demo."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    killer_demo_path = os.path.join(script_dir, "killer_demo.py")
    
    if not os.path.exists(killer_demo_path):
        print("❌ Killer demo not found!")
        return False
    
    print("🎬 LAUNCHING KILLER DEMO...")
    print("🔴 RECORD THIS! Use OBS Studio or any screen recorder")
    print("📹 Record at 1080p with audio commentary")
    print()
    input("Press Enter when you're ready to record (and recording has started)...")
    print()
    print("🚀 STARTING DEMO IN 3... 2... 1...")
    print()
    
    try:
        result = subprocess.run([sys.executable, killer_demo_path], 
                              capture_output=False, 
                              text=True)
        
        print()
        print("🎬 DEMO COMPLETE!")
        
        if result.returncode == 0:
            print("✅ Demo ran successfully!")
            print("📹 If you recorded this, you have LAUNCH GOLD!")
            return True
        else:
            print(f"⚠️ Demo completed with exit code: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running demo: {e}")
        return False

def open_launch_resources():
    """Open useful launch resources."""
    print("🌐 OPENING LAUNCH RESOURCES...")
    
    resources = [
        ("YouTube Upload", "https://youtube.com/upload"),
        ("Medium Write", "https://medium.com/new-story"),
        ("Dev.to Write", "https://dev.to/new"),
        ("Hacker News Submit", "https://news.ycombinator.com/submit"),
        ("Reddit r/MachineLearning", "https://reddit.com/r/MachineLearning"),
        ("Twitter Compose", "https://twitter.com/compose/tweet"),
        ("LinkedIn Post", "https://linkedin.com/feed")
    ]
    
    print("Opening these resources in your browser:")
    for name, url in resources:
        print(f"   🔗 {name}")
    
    print()
    choice = input("Open all resources? (y/n): ").strip().lower()
    
    if choice == 'y':
        for name, url in resources:
            try:
                webbrowser.open(url)
                print(f"✅ Opened {name}")
            except Exception as e:
                print(f"❌ Failed to open {name}: {e}")
    else:
        print("💡 You can open these manually when ready")

def create_launch_checklist():
    """Create a personalized launch checklist."""
    print("📋 CREATING YOUR LAUNCH CHECKLIST...")
    
    checklist = {
        "launch_date": datetime.now().isoformat(),
        "creator": "Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)",
        "project": "MAPLE - Multi Agent Protocol Language Engine",
        "checklist": [
            {
                "task": "Record killer demo video",
                "estimated_time": "30 minutes",
                "completed": False,
                "notes": "Use OBS Studio, 1080p, with audio commentary"
            },
            {
                "task": "Upload video to YouTube",
                "estimated_time": "15 minutes", 
                "completed": False,
                "notes": "Title: 'MAPLE: A Multi-Agent Communication Protocol'"
            },
            {
                "task": "Publish blog post on Medium",
                "estimated_time": "15 minutes",
                "completed": False,
                "notes": "Use the provided blog post template"
            },
            {
                "task": "Post Twitter thread",
                "estimated_time": "10 minutes",
                "completed": False,
                "notes": "10-tweet thread with video link"
            },
            {
                "task": "Submit to Hacker News",
                "estimated_time": "5 minutes",
                "completed": False,
                "notes": "Show HN format with demo link"
            },
            {
                "task": "Post on r/MachineLearning",
                "estimated_time": "5 minutes",
                "completed": False,
                "notes": "Technical focus, performance numbers"
            },
            {
                "task": "Share on LinkedIn",
                "estimated_time": "5 minutes",
                "completed": False,
                "notes": "Professional network, enterprise angle"
            },
            {
                "task": "Engage with early responses",
                "estimated_time": "ongoing",
                "completed": False,
                "notes": "Reply to comments, answer questions"
            }
        ],
        "success_metrics": {
            "24_hour_targets": {
                "github_stars": 100,
                "youtube_views": 1000,
                "twitter_impressions": 10000,
                "hacker_news_points": 50
            },
            "1_week_targets": {
                "github_stars": 500,
                "early_adopters": 10,
                "media_mentions": 3
            }
        }
    }
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    checklist_path = os.path.join(script_dir, "launch_checklist.json")
    
    with open(checklist_path, 'w') as f:
        json.dump(checklist, f, indent=2)
    
    print(f"✅ Launch checklist created: {checklist_path}")
    print()
    print("📋 YOUR LAUNCH SEQUENCE:")
    for i, item in enumerate(checklist["checklist"], 1):
        print(f"   {i}. {item['task']} ({item['estimated_time']})")
    print()
    print("🎯 24-HOUR TARGETS:")
    targets = checklist["success_metrics"]["24_hour_targets"]
    for metric, target in targets.items():
        print(f"   • {metric.replace('_', ' ').title()}: {target:,}")

def launch_mission_control():
    """Main launch mission control interface."""
    print_mission_banner()
    
    print("🎯 WELCOME TO MAPLE LAUNCH COMMAND CENTER!")
    print("Ready to introduce MAPLE to the world?")
    print()
    
    while True:
        print("🚀 LAUNCH MENU:")
        print("=" * 40)
        print("1. 🔍 Check Launch Readiness")
        print("2. 🎬 Run Killer Demo (RECORD THIS!)")
        print("3. 📋 Create Launch Checklist")
        print("4. 🌐 Open Launch Resources")
        print("5. 📖 View Launch Package")
        print("6. 🚀 EXECUTE FULL LAUNCH SEQUENCE")
        print("0. 👋 Exit")
        print()
        
        choice = input("🎯 Select option (0-6): ").strip()
        
        if choice == "1":
            print()
            ready = check_launch_readiness()
            if ready:
                print("🚀 You're ready to launch MAPLE!")
            else:
                print("💡 Address the issues above and check again")
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            print()
            success = run_killer_demo()
            if success:
                print("🎉 Amazing demo! Ready for the world!")
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            print()
            create_launch_checklist()
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            print()
            open_launch_resources()
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            print()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            package_path = os.path.join(script_dir, "LAUNCH_PACKAGE.md")
            
            if os.path.exists(package_path):
                print("📖 Opening launch package...")
                if os.name == 'nt':  # Windows
                    os.startfile(package_path)
                else:  # macOS/Linux
                    subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', package_path])
            else:
                print("❌ Launch package not found!")
            input("\nPress Enter to continue...")
            
        elif choice == "6":
            print()
            print("🚀 FULL LAUNCH SEQUENCE INITIATED!")
            print("⚠️ This will guide you through every step")
            print()
            
            confirm = input("Are you ready to launch MAPLE? (yes/no): ").strip().lower()
            if confirm == "yes":
                print()
                print("🎬 Step 1: First, let's run the killer demo...")
                input("Press Enter to continue...")
                
                demo_success = run_killer_demo()
                if demo_success:
                    print()
                    print("🌐 Step 2: Opening all launch resources...")
                    open_launch_resources()
                    print()
                    print("📋 Step 3: Creating your checklist...")
                    create_launch_checklist()
                    print()
                    print("🎯 LAUNCH SEQUENCE COMPLETE!")
                    print("Follow the checklist and make history!")
                    break
                else:
                    print("❌ Demo had issues. Fix and try again.")
            else:
                print("💡 Come back when you're ready to change the world!")
            
        elif choice == "0":
            print()
            print("🌟 Thank you for building the future!")
            print("MAPLE Creator: Mahesh Vaikri")
            print("🚀 The world is waiting for MAPLE!")
            break
            
        else:
            print("❌ Invalid choice. Try again.")
        
        print()

def main():
    """Launch mission control."""
    try:
        launch_mission_control()
    except KeyboardInterrupt:
        print("\n\n👋 Launch aborted by user.")
        print("🌟 MAPLE Creator: Mahesh Vaikri")
        print("🚀 Ready to launch when you are!")
    except Exception as e:
        print(f"\n❌ Launch control error: {e}")
        print("💡 Try restarting the launch control system")

if __name__ == "__main__":
    main()
