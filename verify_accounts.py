from app import create_app, db
from app.models import Account

app = create_app()

with app.app_context():
    # Use the same user_id as implied in the app (first one found or fixed)
    # We will just query all accounts
    accounts = Account.query.all()
    print(f"Total accounts in DB: {len(accounts)}")
    
    for acc in accounts:
        classif = acc.get_classification()
        print(f"Account: {acc.email_google} | Classification: {classif} | Anthropic: {acc.is_anthropic_available()} | Gemini: {acc.is_gemini_available()}")
        
    # Check filtering logic specifically for 'disponible'
    disponibles = [a for a in accounts if a.get_classification() == 'disponible']
    print(f"\nFiltered 'disponible' count: {len(disponibles)}")
