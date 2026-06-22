# Static catalog of common n8n nodes for the workflow planner.
# This list is maintained independently — no runtime dependency on n8n API.
NODES_CATALOG: list[dict] = [
    # Triggers
    {"node_type": "n8n-nodes-base.webhook", "display_name": "Webhook", "description": "Starts workflow on HTTP request", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.scheduleTrigger", "display_name": "Schedule Trigger", "description": "Starts workflow on a schedule (cron)", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.emailReadImap", "display_name": "Email Trigger (IMAP)", "description": "Triggers when a new email arrives", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.slackTrigger", "display_name": "Slack Trigger", "description": "Triggers on Slack events", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.formTrigger", "display_name": "n8n Form Trigger", "description": "Starts workflow when a form is submitted", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.chatTrigger", "display_name": "Chat Trigger", "description": "Starts workflow from chat message", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.manualTrigger", "display_name": "Manual Trigger", "description": "Starts workflow manually", "category": ["Core Nodes"]},

    # HTTP / API
    {"node_type": "n8n-nodes-base.httpRequest", "display_name": "HTTP Request", "description": "Makes HTTP requests to any API", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.respondToWebhook", "display_name": "Respond to Webhook", "description": "Sends response back to webhook caller", "category": ["Core Nodes"]},

    # Data transformation
    {"node_type": "n8n-nodes-base.code", "display_name": "Code", "description": "Runs custom JavaScript or Python code", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.set", "display_name": "Edit Fields (Set)", "description": "Sets or transforms field values", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.if", "display_name": "If", "description": "Routes data based on a condition", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.switch", "display_name": "Switch", "description": "Routes data to different branches", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.merge", "display_name": "Merge", "description": "Merges data from multiple branches", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.splitInBatches", "display_name": "Loop Over Items", "description": "Loops over items in batches", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.aggregate", "display_name": "Aggregate", "description": "Combines multiple items into one", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.filter", "display_name": "Filter", "description": "Filters items based on conditions", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.itemLists", "display_name": "Item Lists", "description": "Manipulates lists of items", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.removeDuplicates", "display_name": "Remove Duplicates", "description": "Removes duplicate items", "category": ["Core Nodes"]},
    {"node_type": "n8n-nodes-base.dateTime", "display_name": "Date & Time", "description": "Manipulates date and time values", "category": ["Core Nodes"]},

    # Communication
    {"node_type": "n8n-nodes-base.emailSend", "display_name": "Send Email", "description": "Sends an email via SMTP", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.slack", "display_name": "Slack", "description": "Sends messages and manages Slack", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.telegram", "display_name": "Telegram", "description": "Sends Telegram messages", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.whatsApp", "display_name": "WhatsApp Business Cloud", "description": "Sends WhatsApp messages", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.gmail", "display_name": "Gmail", "description": "Reads and sends Gmail emails", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.microsoftOutlook", "display_name": "Microsoft Outlook", "description": "Manages Outlook email and calendar", "category": ["Communication"]},
    {"node_type": "n8n-nodes-base.twilio", "display_name": "Twilio", "description": "Sends SMS via Twilio", "category": ["Communication"]},

    # Database
    {"node_type": "n8n-nodes-base.postgres", "display_name": "Postgres", "description": "Reads and writes to PostgreSQL", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.mysql", "display_name": "MySQL", "description": "Reads and writes to MySQL", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.mongodb", "display_name": "MongoDB", "description": "Reads and writes to MongoDB", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.redis", "display_name": "Redis", "description": "Reads and writes to Redis", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.spreadsheetFile", "display_name": "Spreadsheet File", "description": "Reads and writes Excel/CSV files", "category": ["Data & Storage"]},

    # Cloud storage
    {"node_type": "n8n-nodes-base.googleDrive", "display_name": "Google Drive", "description": "Manages files in Google Drive", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.googleSheets", "display_name": "Google Sheets", "description": "Reads and writes Google Sheets", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.microsoftOneDrive", "display_name": "Microsoft OneDrive", "description": "Manages files in OneDrive", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.dropbox", "display_name": "Dropbox", "description": "Manages files in Dropbox", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.s3", "display_name": "AWS S3", "description": "Manages files in Amazon S3", "category": ["Data & Storage"]},

    # CRM / Business
    {"node_type": "n8n-nodes-base.hubspot", "display_name": "HubSpot", "description": "Manages HubSpot CRM contacts and deals", "category": ["Sales"]},
    {"node_type": "n8n-nodes-base.salesforce", "display_name": "Salesforce", "description": "Manages Salesforce CRM data", "category": ["Sales"]},
    {"node_type": "n8n-nodes-base.notion", "display_name": "Notion", "description": "Creates and updates Notion pages", "category": ["Productivity"]},
    {"node_type": "n8n-nodes-base.airtable", "display_name": "Airtable", "description": "Reads and writes Airtable records", "category": ["Data & Storage"]},
    {"node_type": "n8n-nodes-base.trello", "display_name": "Trello", "description": "Manages Trello boards and cards", "category": ["Productivity"]},
    {"node_type": "n8n-nodes-base.jira", "display_name": "Jira", "description": "Creates and updates Jira issues", "category": ["Development"]},
    {"node_type": "n8n-nodes-base.github", "display_name": "GitHub", "description": "Manages GitHub repos, issues, PRs", "category": ["Development"]},

    # AI / LangChain
    {"node_type": "@n8n/n8n-nodes-langchain.agent", "display_name": "AI Agent", "description": "AI agent that uses tools to complete tasks", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.lmChatMisikaAi", "display_name": "Mistika-AI Chat Model", "description": "Mistika-AI LLM for chat and completion", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.chainLlm", "display_name": "Basic LLM Chain", "description": "Runs a prompt through an LLM", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.chainRetrievalQa", "display_name": "Question and Answer Chain", "description": "Answers questions from a document store", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.toolCode", "display_name": "Code Tool", "description": "Gives AI agent a custom code tool", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.toolHttpRequest", "display_name": "HTTP Request Tool", "description": "Gives AI agent an HTTP request tool", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.toolWorkflow", "display_name": "Call n8n Workflow Tool", "description": "Gives AI agent access to an n8n workflow", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.memoryBufferWindow", "display_name": "Window Buffer Memory", "description": "Stores recent chat history for AI agent", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.embeddingsOpenAi", "display_name": "Embeddings", "description": "Generates text embeddings for vector search", "category": ["AI"]},
    {"node_type": "@n8n/n8n-nodes-langchain.vectorStoreInMemory", "display_name": "In-Memory Vector Store", "description": "Stores and retrieves vectors in memory", "category": ["AI"]},
]
