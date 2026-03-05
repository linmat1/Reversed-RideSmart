# Onboarding: Adding a New Account

## Step 1: Install Proxyman

Download **Proxyman** from the App Store on your iPhone and complete the initial setup, including:

- Downloading and installing the Proxyman certificate
- Enabling root certificate trust: **Settings → General → About → Certificate Trust Settings**, then toggle on full trust for Proxyman

## Step 2: Start the VPN

In Proxyman, start the VPN. This routes your phone's traffic through Proxyman so it can be inspected.

## Step 3: Find the RideSmart Domain

Navigate to the domain (in the Proxyman app):

```
router-ucaca.live.ridewithvia.com
```

Then enable **SSL Proxying** on it. This lets Proxyman decrypt and read the request bodies for that domain.

## Step 4: Capture the Request

1. Open the **RideSmart app** and book any ride, then cancel it
2. Go back to Proxyman and find the request URL ending in:
   ```
   /prescheduled/recurring/get
   ```
3. Tap it, go to **Request → Body**, and copy the entire contents

Send that to me to add the account.
