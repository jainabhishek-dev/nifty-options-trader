# Railway Deployment Guide
**Last Updated:** December 24, 2025

## Overview
This guide walks you through deploying the Nifty Options Trader to Railway.app for 24/7 operation.

---

## Prerequisites Checklist
- [x] All code changes committed to git
- [x] Procfile created
- [x] Flask app configured for production
- [ ] Railway account created
- [ ] Environment variables ready
- [ ] Kite redirect URL updated

---

## Step 1: Create Railway Account (5 minutes)

1. Go to https://railway.app
2. Click "Start a New Project"
3. Sign in with GitHub (recommended) or email
4. **Important:** Add payment method to get:
   - $5 free credits (valid for 30 days)
   - After trial: $5/month plan (sufficient for your usage)

---

## Step 2: Deploy from GitHub (2 minutes)

1. In Railway dashboard, click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose repository: `jainabhishek-dev/nifty-options-trader`
4. Railway will:
   - Detect Python project
   - Use Procfile
   - Assign a URL like: `https://nifty-options-trader-production.up.railway.app`

---

## Step 3: Set Environment Variables (5 minutes)

In Railway dashboard → Your Project → Variables tab, add these:

```
ENVIRONMENT=production
PORT=5000
FLASK_SECRET_KEY=your_secret_key_from_local_env
KITE_API_KEY=21otiwmgilmaxvva
KITE_API_SECRET=your_secret_from_local_env
KITE_REDIRECT_URL=https://nifty-options-trader-production.up.railway.app/auth
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

**Where to find these values:**
- Open your local `.env` file
- Copy values exactly (don't include quotes)
- Replace `KITE_REDIRECT_URL` with your Railway URL (you'll get this after deployment)

---

## Step 4: Update Kite Dashboard (2 minutes)

1. Go to https://developers.kite.trade
2. Login → Select "Nifty_Options_Trader" app
3. Edit "Redirect URL" field:
   
   **Before:**
   ```
   http://127.0.0.1:5000/auth
   ```
   
   **After (comma-separated):**
   ```
   http://127.0.0.1:5000/auth, https://nifty-options-trader-production.up.railway.app/auth
   ```
   
4. Click "Update" to save

**Why keep localhost?**
- You can still test locally
- Both URLs work simultaneously

---

## Step 5: Test Deployment (3 minutes)

1. Open Railway URL: `https://nifty-options-trader-production.up.railway.app`
2. You should see "Login with Kite" button
3. Click login → Authenticate → Should redirect back successfully
4. Check dashboard loads correctly
5. Try starting a strategy (during market hours)

---

## Daily Workflow (After Deployment)

### Morning (Before Market Opens)
1. Open Railway URL from **any device** (laptop, phone, tablet)
2. Click "Login with Kite" (token expires daily at 3:30 PM)
3. Authenticate on Kite
4. Start your scalping strategy
5. Close browser/device - **app keeps running on Railway!**

### During Market Hours (9:15 AM - 3:30 PM)
- Monitor from anywhere: https://nifty-options-trader-production.up.railway.app
- Check positions, orders, P&L
- Pages auto-refresh every 15 seconds

### After Market Close
- Review daily P&L
- Check trade history
- No action needed - app stays running

---

## Cost Monitoring

**Railway Pricing:**
- First 30 days: **$5 free credits**
- After trial: **$5/month plan**
- Your expected usage: **$5-9/month** (well within plan)

**Usage Breakdown:**
- Trading hours: 6.25 hours/day × 20 days = 125 hours/month
- Cost: ~$0.03/hour = **~$3.75/month**
- Database: Supabase (already free forever)
- Total: **$5/month sufficient**

**To monitor usage:**
1. Railway dashboard → Your Project → Usage tab
2. Check "Current Usage" daily
3. Set up billing alerts (optional)

---

## Troubleshooting

### Issue: Can't login with Kite
**Solution:** Check Railway environment variable `KITE_REDIRECT_URL` matches URL in Kite dashboard

### Issue: "Authentication required" error
**Solution:** Re-authenticate every morning (Kite tokens expire daily at 3:30 PM)

### Issue: Strategy not starting
**Solution:** 
1. Check Railway logs: Dashboard → Your Project → Deployments → Latest → Logs
2. Verify database connection (Supabase should be running)

### Issue: Database errors
**Solution:** Check `SUPABASE_URL` and `SUPABASE_KEY` in Railway variables

---

## Important Notes

1. **Kite Subscription Expiry:** Your Kite Connect subscription expires **09 Jan 2026**
   - Extend before expiry to avoid trading disruption
   - Go to https://developers.kite.trade → Subscription tab
   
2. **Daily Authentication:** Kite access tokens expire at 3:30 PM IST
   - You must re-authenticate every morning before market opens
   - This is a Kite security requirement (cannot be bypassed)
   
3. **Browser Access:** Works on all devices
   - Laptop, desktop, tablet, phone
   - Any browser (Chrome, Safari, Firefox)
   - No VPN needed
   
4. **Data Persistence:** All data stored in Supabase
   - Trade history preserved
   - Position records maintained
   - Safe even if Railway restarts

---

## Next Steps

After successful deployment:
1. ✅ Test authentication flow
2. ✅ Verify strategy activation
3. ✅ Monitor first day of live trading
4. ✅ Set up cost monitoring
5. ✅ Bookmark Railway URL for easy access

---

## Support Resources

- **Railway Docs:** https://docs.railway.app
- **Kite API Docs:** https://kite.trade/docs/connect/v3
- **Supabase Docs:** https://supabase.com/docs

---

**Deployment Time Estimate:** 15-20 minutes total
**Monthly Cost:** $5 (after $5 free trial)
**Uptime:** 24/7 (no laptop needed)
