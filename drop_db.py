import os
import time

db_path = ""

for i in range(5):
    try:
        os.remove(db_path)
        print(f"Baza danych '{db_path}' została usunięta.")
        break
    except PermissionError:
        print(f"⚠️ Baza jest w użyciu, próba {i+1}/5...")
        time.sleep(1)
else:
    print("❌ Nie udało się usunąć bazy — plik nadal otwarty.")
