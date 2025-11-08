#!/usr/bin/env python3
"""
Prompt Validation Script

Validates that all required prompt files exist and can be loaded properly.
Run this script to ensure the prompt migration was successful.

Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: info@promptrca.com
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from promptrca.utils.prompt_loader import validate_prompts, list_available_prompts, load_prompt


def main():
    """Main validation function."""
    print("🔍 PromptRCA Prompt Validation")
    print("=" * 50)
    
    # List available prompts
    available = list_available_prompts()
    print(f"📁 Available prompt files: {len(available)}")
    for prompt in available:
        print(f"   ✓ {prompt}.md")
    print()
    
    # Validate all expected prompts
    print("🔍 Validating required prompts...")
    results = validate_prompts()
    
    all_valid = True
    for prompt_name, exists in results.items():
        status = "✅" if exists else "❌"
        print(f"   {status} {prompt_name}")
        if not exists:
            all_valid = False
    
    print()
    
    if all_valid:
        print("🎉 All prompts validated successfully!")
        print("✅ The prompt migration is complete and working.")
        
        # Test loading a sample prompt
        try:
            sample_prompt = load_prompt("trace_specialist")
            print(f"📝 Sample prompt loaded: {len(sample_prompt)} characters")
            print("✅ Prompt loading is working correctly.")
        except Exception as e:
            print(f"❌ Error loading sample prompt: {e}")
            all_valid = False
    else:
        print("❌ Some prompts are missing!")
        print("Please ensure all .md files are created in src/promptrca/prompts/")
    
    print()
    print("📊 Summary:")
    print(f"   Total prompts: {len(results)}")
    print(f"   Valid: {sum(results.values())}")
    print(f"   Missing: {len(results) - sum(results.values())}")
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)