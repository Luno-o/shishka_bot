import sys
print("1. Начало импорта services")
sys.stdout.flush()

try:
    import services
    print("2. services импортирован")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("3. Конец")
