from app import create_app, db

def test_api():
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Mock session by modifying it directly or using a helper if available
        # Since we have @api_require_unlock, we need session['unlocked'] = True
        with client.session_transaction() as sess:
            sess['unlocked'] = True
            # We also need a user context if g.user_id is used.
            # In single user mode, g.user_id is usually set in before_request or hardcoded.
            # Let's see how authentication works.
            
        # The app uses a hardcoded SINGLE_USER_ID in models, so g.user_id might need to be set
        # However, looking at models.py: SINGLE_USER_ID = "00000000-0000-0000-0000-000000000000"
        
        # Let's try the request
        response = client.get('/api/accounts?filter=disponible')
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.get_json()
            print(f"Total Accounts: {data.get('total')}")
            print("Accounts Found:")
            for acc in data.get('accounts', []):
                print(f" - {acc['email_google']} ({acc['classification']})")
        else:
            print(f"Error: {response.data}")

if __name__ == "__main__":
    test_api()
