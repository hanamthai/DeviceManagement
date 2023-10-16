# "orderdrink_api_flask_env\Scripts\activate" to activate enviroments of packet
# "orderdrink_api_flask_env\Scripts\deactivate" to deactivate enviroments of packet
# app.py
import os
from devicemanage import app

if __name__ == "__main__":
    app.run(
        debug=True,
        host=os.environ.get('IP') or '0.0.0.0',
        port=int(os.environ.get('PORT') or 5000)
    )
