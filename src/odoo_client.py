import logging
import time
import xmlrpc.client
from functools import wraps

logger = logging.getLogger(__name__)


def retry(max_attempts=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError) as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
        return wrapper
    return decorator


class OdooClient:
    def __init__(self, url: str, db: str, username: str, api_key: str):
        self.url = url
        self.db = db
        self.username = username
        self.api_key = api_key
        self.uid = None
        self.models = None

    @retry()
    def authenticate(self):
        """Odoo XML-RPCで認証し、UIDを取得する"""
        common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common"
        )
        self.uid = common.authenticate(
            self.db, self.username, self.api_key, {}
        )
        if not self.uid:
            raise RuntimeError("Odoo認証に失敗しました")
        self.models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object"
        )
        logger.info("Odoo認証成功 (uid=%s)", self.uid)

    @retry()
    def search_read(self, model: str, domain: list,
                    fields: list, limit: int = 0) -> list:
        """指定モデルをsearch_readで取得"""
        kwargs = {'fields': fields}
        if limit:
            kwargs['limit'] = limit
        return self.models.execute_kw(
            self.db, self.uid, self.api_key,
            model, 'search_read',
            [domain],
            kwargs
        )

    def get_sale_order_lines(self, partner_name: str) -> list:
        """指定取引先の有効な販売オーダー明細を取得"""
        domain = [
            ['order_id.partner_id.name', '=', partner_name],
            ['order_id.state', 'in', ['sale', 'done']],
        ]
        lines = self.search_read(
            'sale.order.line', domain,
            ['name', 'price_unit', 'product_id']
        )
        logger.info(
            "%s 販売オーダー明細取得 (%d件)", partner_name, len(lines)
        )
        return lines

    def get_timesheets(self, project_name: str,
                       year: int, month: int,
                       last_day: str) -> list:
        """指定プロジェクトの当月タイムシートエントリを取得"""
        domain = [
            ['project_id.name', 'ilike', project_name],
            ['date', '>=', f'{year}-{month:02d}-01'],
            ['date', '<=', last_day],
        ]
        timesheets = self.search_read(
            'account.analytic.line', domain,
            ['date', 'unit_amount', 'name', 'task_id']
        )
        logger.info(
            "%s タイムシート取得 (%d件)", project_name, len(timesheets)
        )
        return timesheets
