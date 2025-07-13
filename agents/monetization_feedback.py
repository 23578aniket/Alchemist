# agents/monetization_feedback.py
import json
import requests
from datetime import datetime, timedelta
from config.settings import (
    ADSENSE_PUBLISHER_ID, ADSENSE_AD_SLOT_ID, AMAZON_ASSOCIATES_TAG,
    NICHE_TOPIC, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
)
from database.db_manager import DBManager
from database.models import GeneratedContent, PublishedContent, PerformanceMetric
from utils.logger import setup_logger
from utils.llm_interface import LLMInterface
from utils.prompt_templates import AFFILIATE_LINK_OPPORTUNITY_PROMPT, PERFORMANCE_ANALYSIS_PROMPT
import random

logger = setup_logger("MonetizationFeedbackAgent")
db_manager = DBManager()
llm_interface = LLMInterface()


class MonetizationFeedbackAgent:
    """
    Agent responsible for injecting monetization elements into content
    and analyzing performance metrics to provide optimization feedback.
    """

    def inject_monetization(self, generated_content_id: int) -> str | None:
        """
        Injects AdSense code and Amazon India affiliate links into the content's HTML.
        Returns the monetized HTML, or None on failure.
        """
        content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not content:
            logger.error(f"Content {generated_content_id} not found for monetization injection.")
            return None
        if content.status == "MONETIZED" or content.status == "PUBLISHED":
            logger.info(f"Content {generated_content_id} already monetized. Skipping.")
            return content.body_html

        logger.info(f"Injecting monetization into content ID: {generated_content_id}")

        monetized_html = content.body_html

        # 1. AdSense Injection (simple heuristic for example)
        if ADSENSE_PUBLISHER_ID and ADSENSE_AD_SLOT_ID:
            ad_code_unit = f"""
            <div class="ad-unit" style="margin: 20px auto; text-align: center;">
                <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-{ADSENSE_PUBLISHER_ID}" crossorigin="anonymous"></script>
                <ins class="adsbygoogle"
                     style="display:block; text-align:center;"
                     data-ad-layout="in-article"
                     data-ad-format="fluid"
                     data-ad-slot="{ADSENSE_AD_SLOT_ID}"></ins>
                <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
            </div>
            """

            # Inject ad unit after every 3rd paragraph
            paragraphs = monetized_html.split('</p>')
            new_paragraphs = []
            for i, p in enumerate(paragraphs):
                new_paragraphs.append(p)
                if (i + 1) % 3 == 0 and i < len(paragraphs) - 1:  # Inject every 3rd paragraph
                    new_paragraphs.append(ad_code_unit)
            monetized_html = '</p>'.join(new_paragraphs)
            logger.info(f"AdSense code injected into content {generated_content_id}.")
        else:
            logger.warning("AdSense credentials not fully configured. Skipping AdSense injection.")

        # 2. Affiliate Link Injection (Amazon India)
        if AMAZON_ASSOCIATES_TAG:
            prompt = AFFILIATE_LINK_OPPORTUNITY_PROMPT.format(
                language_name=content.language,
                article_text=content.body_html[:5000]  # Limit input to LLM token window
            )
            affiliate_suggestions_json = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=500,
                                                                     temperature=0.5)

            try:
                affiliate_suggestions = json.loads(affiliate_suggestions_json).get("affiliate_links", [])
                for link_data in affiliate_suggestions:
                    keyword = link_data.get('keyword')
                    amazon_search_term = link_data.get('amazon_search_term', keyword)
                    if keyword and amazon_search_term:
                        # Dynamically generate Amazon affiliate search link
                        affiliate_link = f"https://www.amazon.in/s?k={amazon_search_term.replace(' ', '+')}&tag={AMAZON_ASSOCIATES_TAG}"
                        # Replace only first occurrence of keyword to avoid over-linking
                        monetized_html = monetized_html.replace(keyword,
                                                                f'<a href="{affiliate_link}" target="_blank" rel="sponsored noopener noreferrer">{keyword}</a>',
                                                                1)
                        logger.info(f"Injected affiliate link for '{keyword}'.")

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse affiliate suggestions JSON for {generated_content_id}: {e} -> {affiliate_suggestions_json[:500]}")
            except Exception as e:
                logger.error(f"Error during affiliate link injection for {generated_content_id}: {e}")
        else:
            logger.warning("Amazon Associates Tag not configured. Skipping affiliate link injection.")

        # Update the content in the database with the monetized HTML
        content.body_html = monetized_html
        content.status = "MONETIZED"
        db_manager.update_record(content)
        logger.info(f"Monetization injected for content ID: {generated_content_id}.")
        return monetized_html

    def sell_digital_product(self, generated_content_id: int, product_name: str, amount_in_paise: int) -> str | None:
        """
        Creates a Razorpay payment link for a digital product related to the content.
        This is a simplified example.
        """
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            logger.warning("Razorpay credentials not configured. Skipping digital product sales.")
            return None

        content = db_manager.get_record_by_id(GeneratedContent, generated_content_id)
        if not content:
            logger.error(f"Content {generated_content_id} not found for digital product sale.")
            return None

        logger.info(f"Creating Razorpay order for content ID: {generated_content_id}, product: {product_name}")

        order_url = "https://api.razorpay.com/v1/orders"
        auth = (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)

        order_payload = {
            "amount": amount_in_paise,  # in paise
            "currency": "INR",
            "receipt": f"receipt_{generated_content_id}_{datetime.now().timestamp()}",
            "payment_capture": 1  # Auto capture payment
        }

        try:
            response = requests.post(order_url, auth=auth, json=order_payload, timeout=30)
            response.raise_for_status()
            order_data = response.json()
            order_id = order_data.get('id')

            # In a real scenario, you'd create a payment page or embed a Razorpay checkout.
            # For automation, you might generate a direct payment link if Razorpay supports it for orders.
            # Or, you'd update the content with a button that triggers a JS checkout.

            # For simplicity, returning the order ID as a placeholder for a "link"
            payment_link = f"https://dashboard.razorpay.com/app/orders/{order_id}"

            # You would then need to update the content (e.g., add a "Buy Now" button with this link)
            # This requires updating content.body_html and then re-publishing or updating the page.
            # For now, we'll just log the link.
            logger.info(f"Razorpay order created for {generated_content_id}: {payment_link}")
            return payment_link

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Razorpay order creation failed for {generated_content_id}: {e} - Response: {getattr(e, 'response', 'No response').text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Razorpay integration for {generated_content_id}: {e}")
            return None

    def collect_performance_metrics(self):
        """
        Collects performance data from various APIs (GA4, AdSense, etc.) and stores it.
        This is a scheduled task that runs periodically.
        """
        logger.info("Collecting performance metrics...")

        # --- Placeholder for actual API integrations ---
        # 1. Google Analytics 4 Data (via BigQuery export or GA4 Data API)
        # Requires `google-analytics-data` library and proper GCP authentication.
        # Example:
        # from google.analytics.data_v1beta import BetaAnalyticsDataClient
        # from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
        # client = BetaAnalyticsDataClient()
        # request = RunReportRequest(
        #     property=f"properties/{GA4_PROPERTY_ID}",
        #     date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        #     dimensions=[Dimension(name="pagePath")],
        #     metrics=[Metric(name="activeUsers"), Metric(name="totalRevenue")]
        # )
        # response = client.run_report(request)
        # for row in response.rows:
        #   page_path = row.dimension_values[0].value
        #   views = float(row.metric_values[0].value)
        #   revenue = float(row.metric_values[1].value)
        #   # Map page_path to published_content_id and save to DB

        # 2. AdSense Revenue Data (AdSense Management API)
        # Requires `google-api-python-client` and OAuth.
        # Example:
        # service = build('adsense', 'v2', credentials=credentials)
        # result = service.accounts().reports().generate(
        #     accountId='pub-YOUR_PUBLISHER_ID',
        #     startDate='2024-06-01', endDate='2024-06-30',
        #     metrics=['ESTIMATED_EARNINGS'],
        #     dimensions=['DATE']
        # ).execute()
        # # Process result and save to DB

        # 3. Amazon Associates Data (Reporting API)
        # 4. Razorpay Sales Data (Razorpay API)
        # Example:
        # response = requests.get("https://api.razorpay.com/v1/payments", auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        # payments = response.json()['items']
        # # Process payments, link to generated_content_id via receipt ID if possible

        # --- Simulated Data for Blueprint ---
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)  # Collect for last 24 hours

        published_items = db_manager.get_published_content_for_metrics()
        for item in published_items:
            # Generate dummy data for views, clicks, revenue based on content ID
            # In a real system, these would come from actual analytics APIs
            views = abs(hash(item.external_url) % 5000) + 100  # Min 100 views
            revenue_usd = (views / 1000) * random.uniform(0.5, 2.0)  # Example RPM $0.5 to $2.0 per 1000 views

            # Store views
            db_manager.insert_record(PerformanceMetric(
                published_content_id=item.id,
                metric_type="VIEWS",
                value=float(views),
                timestamp=datetime.utcnow()
            ))
            # Store revenue
            db_manager.insert_record(PerformanceMetric(
                published_content_id=item.id,
                metric_type="REVENUE_USD",
                value=float(revenue_usd),
                timestamp=datetime.utcnow()
            ))
            logger.debug(
                f"Collected simulated metrics for {item.external_url}: Views={views}, Revenue=${revenue_usd:.2f}")

        logger.info("Performance metrics collection complete.")

    def analyze_and_optimize(self):
        """
        Analyzes performance metrics and generates optimization directives for other agents.
        This is the 'brain' of the feedback loop.
        """
        logger.info("Analyzing performance and generating optimization directives.")

        # Fetch recent performance data (e.g., last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        session = db_manager.get_session()
        try:
            recent_metrics = session.query(PerformanceMetric).filter(
                PerformanceMetric.timestamp >= seven_days_ago).all()
        finally:
            session.close()

        # Aggregate metrics by content ID
        content_performance_data = {}
        for metric in recent_metrics:
            if metric.published_content_id not in content_performance_data:
                content_performance_data[metric.published_content_id] = {"VIEWS": [], "REVENUE_USD": []}
            content_performance_data[metric.published_content_id][metric.metric_type].append(metric.value)

        # Calculate averages for analysis
        for content_id, metrics in content_performance_data.items():
            metrics["AVG_VIEWS"] = sum(metrics["VIEWS"]) / len(metrics["VIEWS"]) if metrics["VIEWS"] else 0
            metrics["AVG_REVENUE_USD"] = sum(metrics["REVENUE_USD"]) / len(metrics["REVENUE_USD"]) if metrics[
                "REVENUE_USD"] else 0
            # Add more aggregated metrics (e.g., CTR, conversion rate if available)

        # Use LLM to analyze and suggest directives
        prompt = PERFORMANCE_ANALYSIS_PROMPT.format(
            performance_data_json=json.dumps(content_performance_data, indent=2)
        )

        directives_json_str = llm_interface.generate_text(prompt, model_choice="gemini", max_tokens=1000,
                                                          temperature=0.6)

        try:
            directives = json.loads(directives_json_str).get("directives", [])
            if not isinstance(directives, list): raise ValueError("Expected list of directives.")

            for directive in directives:
                logger.info(f"Generated directive: {directive}")
                # In a real system, these directives would be pushed to a Celery queue
                # or a dedicated "directives" table for the Orchestrator to pick up and act upon.
                # For this blueprint, we just log them. The orchestrator will have logic to consume.
                # Example of how an orchestrator might process:
                # if directive['agent'] == 'content_generation':
                #     if directive['action'] == 'generate_more':
                #         # orchestrator.trigger_content_generation(topic=directive['topic_focus'], quantity=directive['quantity'])
                pass  # Placeholder for actual directive processing
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse optimization directives JSON: {e} -> {directives_json_str[:500]}")
        except ValueError as e:
            logger.error(f"Optimization directives validation failed: {e}")
        except Exception as e:
            logger.error(f"Error during analysis and optimization: {e}")
