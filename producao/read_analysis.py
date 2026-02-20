try:
    with open(r'c:\SANITARIOS GABRIEL\ODOO-SNK\producao\analysis_output.txt', 'r', encoding='utf-16le') as f:
        print(f.read(2000))
except Exception as e:
    print(f"Error reading file: {e}")
