# Unfulfilled Orders Automation

An AWS Lambda function that monitors Shopify unfulfilled orders and posts daily notifications to Slack. This automation helps teams stay on top of orders that need attention.

## Overview

This serverless application runs on a schedule (weekdays at noon, US Central time) to:

1. Query Shopify for unfulfilled orders created in the last 30 days but older than 24 hours
2. Format the order details with direct links to the Shopify admin
3. Post a summary to Slack with financial and fulfillment status

The application is built with AWS SAM (Serverless Application Model) and Python 3.12, running on ARM64 architecture.

## Features

- **Scheduled Execution**: Runs automatically every weekday at noon (Central Time)
- **Smart Filtering**: Finds unfulfilled orders that are:
  - Open status
  - Not in pending financial status
  - Created 24+ hours ago (within the last 30 days)
- **Slack Integration**: Posts formatted messages with order links, timestamps, and status information
- **Message Chunking**: Automatically splits large result sets across multiple Slack messages
- **GraphQL Pagination**: Efficiently handles large order volumes using Shopify's GraphQL API

## Prerequisites

- AWS Account
- Shopify Admin API access token
- Slack workspace with a bot token and channel for notifications
- AWS SAM CLI (for local development and deployment)

## Configuration

The application requires the following environment variables:

### Required
- `SHOPIFY_SHOP` - Your Shopify store hostname (e.g., `your-store.myshopify.com`)
- `SHOPIFY_ADMIN_TOKEN` - Shopify Admin API access token
- `SLACK_BOT_TOKEN` - Slack bot token with `chat:write` permission
- `SLACK_CHANNEL_ID` - Target Slack channel ID for notifications

### Optional
- `SHOPIFY_API_VERSION` - Shopify Admin API version (default: `2025-10`)
- `SHOPIFY_ADMIN_STORE_HANDLE` - Store handle for newer Shopify admin links (e.g., `9f5fee`)

## Deployment

### Using SAM CLI

1. **Build the application:**
   ```bash
   sam build
   ```

2. **Deploy with guided setup:**
   ```bash
   sam deploy --guided
   ```

   Follow the prompts to configure parameters. Your responses will be saved to `samconfig.toml`.

3. **Deploy subsequent updates:**
   ```bash
   sam deploy
   ```

### Parameters

When deploying, you'll be prompted for:
- `ShopifyShop` - Shopify store URL
- `ShopifyAdminToken` - API token (stored securely in AWS)
- `ShopifyApiVersion` - API version (optional, defaults to 2025-10)
- `SlackBotToken` - Slack bot token (stored securely in AWS)
- `SlackChannelId` - Target Slack channel

## Local Development

### Setup

1. Install dependencies:
   ```bash
   pip install -r src/requirements.txt
   ```

2. Create a `.env` file with your configuration:
   ```
   SHOPIFY_SHOP=your-store.myshopify.com
   SHOPIFY_ADMIN_TOKEN=your_token_here
   SHOPIFY_API_VERSION=2025-10
   SHOPIFY_ADMIN_STORE_HANDLE=9f5fee
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_CHANNEL_ID=C123456789
   ```

3. Run the application locally:
   ```bash
   python -m unfulfilled_orders.app
   ```

### Testing with SAM

Invoke the Lambda function locally:
```bash
sam local invoke UnfulfilledOrdersFunction --event event.json
```

## Architecture

- **Handler**: [src/unfulfilled_orders/handler.py](src/unfulfilled_orders/handler.py) - AWS Lambda entry point
- **Application Logic**: [src/unfulfilled_orders/app.py](src/unfulfilled_orders/app.py) - Core functionality
- **Template**: [template.yaml](template.yaml) - AWS SAM infrastructure definition
- **Configuration**: [samconfig.toml](samconfig.toml) - SAM deployment settings

## How It Works

1. **Shopify Query**: Uses GraphQL to fetch unfulfilled orders matching the filter criteria
2. **Pagination**: Handles multiple pages of results automatically
3. **Formatting**: Converts order data into readable Slack messages with order links
4. **Slack Posting**: Posts messages with proper formatting and handles size limits by chunking
5. **Logging**: Prints summary of messages posted and orders found

## API Versions

The application uses Shopify's GraphQL Admin API. The API version can be configured but defaults to `2025-10`. Adjust the `SHOPIFY_API_VERSION` parameter if needed for compatibility with your Shopify plan.

## Dependencies

- `requests>=2.31.0` - HTTP library for API calls
- `python-dotenv>=1.0.1` - Environment variable management (development)

## CloudWatch Logs

Monitor execution through AWS CloudWatch:
1. Navigate to CloudWatch Logs
2. Find the log group `/aws/lambda/unfulfilled-orders` (or similar)
3. Review logs for execution status and order counts

## Troubleshooting

- **No orders found**: Check that your filter criteria match your store's order data
- **Slack errors**: Verify bot token has `chat:write` scope and channel exists
- **Shopify errors**: Check API token permissions and store hostname
- **Rate limits**: The function includes delays between Slack posts to avoid rate limiting

## License

This project is provided as-is for internal use.
