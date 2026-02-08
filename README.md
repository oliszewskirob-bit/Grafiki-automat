# Grafiki automat (bootstrap)

Minimalny szkielet projektu pod silnik grafiku TK/MR/ZDO.

## Wymagania
- Python 3.11+

## Instalacja (Windows)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m scheduler --help
```

## Uruchomienie
```powershell
python -m scheduler --input C:\\sciezka\\wejscie.xlsx --month 2024-01 --out C:\\sciezka\\wyjscie.xlsx
```

Po poprawnym starcie CLI wypisze:
```
OK: bootstrap
```
