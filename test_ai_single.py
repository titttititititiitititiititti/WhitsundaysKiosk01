"""Test AI postprocessor on a single RedCat tour"""
import subprocess
import sys

print("Running AI postprocessor on tours_redcatadventures.csv...")
print("=" * 80)

result = subprocess.run(
    [sys.executable, 'ai_postprocess_csv.py', 'tours_redcatadventures.csv'],
    capture_output=False,  # Show output in real-time
    text=True
)

print("=" * 80)
print(f"Exit code: {result.returncode}")

if result.returncode == 0:
    print("\n[OK] AI postprocessor completed")
    print("\nNow run: python merge_cleaned_to_media.py")
    print("Then restart app.py to see the results")
else:
    print(f"\n[ERROR] AI postprocessor failed")


