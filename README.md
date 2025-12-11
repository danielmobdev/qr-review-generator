### Razorpay Setup

1. **Create Webhook in Razorpay Dashboard**
   - Login to [Razorpay Dashboard](https://dashboard.razorpay.com/)
   - Go to **Settings** → **Webhooks**
   - Click **"Add New Webhook"**
   - **Webhook URL**: `https://your-domain.com/api/payment/webhook`
   - **Active Events**: Select `payment.captured`
   - **Webhook Secret**: Copy the generated secret
   - Set as **Active**
   - Click **Save**

2. **Set Webhook Secret**
   - Use the copied webhook secret as `RAZORPAY_WEBHOOK_SECRET` environment variable

### Render Deployment
