# AI credential management

Generate the application encryption key once:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Store the result as `VAYUJIT_CREDENTIAL_ENCRYPTION_KEY` in the deployment
secret store. Never commit it. Stored provider keys use AES-256-GCM, a random
nonce, authenticated version metadata, and a bounded plaintext. A missing,
wrong, or invalid encryption key fails closed.

Saving a replacement encrypts the new value before the transaction completes.
The UI clears the password field and returns only a masked suffix and safe
source label. Removing the application key disables the provider; a deployment
credential may still be reported as configured according to precedence.
Rotate by installing the encryption secret, saving and validating a replacement
provider key, then revoking the old provider key externally.
