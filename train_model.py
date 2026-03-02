import pandas as pd
import re
import pickle
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

# Sample dataset (temporary basic dataset)
data = {
    "url": [
        "http://secure-bank-login.com",
        "https://google.com",
        "http://paypal-verification-alert.com",
        "https://github.com",
        "http://update-your-account-now.net",
        "https://openai.com"
    ],
    "label": [1, 0, 1, 0, 1, 0]  # 1 = Phishing, 0 = Legit
}

df = pd.DataFrame(data)

# Feature extraction function
def extract_features(url):
    return [
        len(url),
        url.count("-"),
        url.count("@"),
        url.count("https"),
        url.count("http"),
        url.count(".")
    ]

X = df["url"].apply(extract_features).tolist()
y = df["label"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = RandomForestClassifier()
model.fit(X_train, y_train)

# Save model
with open("phishing_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model trained and saved successfully 🔥")