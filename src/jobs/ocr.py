"""YomiToku OCR処理"""

import logging
import tempfile
import aiohttp
from pathlib import Path

logger = logging.getLogger(__name__)

# YomiTokuはオプション依存
try:
    from yomitoku import DocumentAnalyzer
    YOMITOKU_AVAILABLE = True
except ImportError:
    YOMITOKU_AVAILABLE = False
    logger.warning("YomiTokuがインストールされていません。画像OCRは無効です。")


class OCRProcessor:
    """OCR処理クラス"""

    def __init__(self):
        self.analyzer = None
        if YOMITOKU_AVAILABLE:
            try:
                # 軽量モデル、CPU推論
                self.analyzer = DocumentAnalyzer(
                    configs={
                        "ocr": {"device": "cpu", "lite": True},
                        "layout": {"device": "cpu"},
                    }
                )
                logger.info("YomiToku初期化完了（軽量モデル、CPU）")
            except Exception as e:
                logger.error(f"YomiToku初期化失敗: {e}")

    def is_available(self) -> bool:
        """OCRが利用可能か"""
        return self.analyzer is not None

    def is_image(self, content_type: str) -> bool:
        """画像ファイルか判定"""
        image_types = [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/gif",
            "image/webp",
        ]
        return content_type.lower() in image_types

    async def download_file(self, url: str) -> bytes | None:
        """ファイルをダウンロード"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.error(f"ダウンロード失敗: {url}, status={response.status}")
                    return None
        except Exception as e:
            logger.error(f"ダウンロードエラー: {url} - {e}")
            return None

    async def extract_text(self, image_data: bytes, filename: str) -> str | None:
        """画像からテキストを抽出"""
        if not self.is_available():
            logger.warning("OCRが利用不可")
            return None

        try:
            # 一時ファイルに保存
            suffix = Path(filename).suffix or ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(image_data)
                temp_path = f.name

            # OCR実行
            result = self.analyzer(temp_path)

            # テキスト抽出
            if hasattr(result, "text"):
                text = result.text
            elif hasattr(result, "to_text"):
                text = result.to_text()
            else:
                # フォールバック: 全テキストブロックを結合
                text_blocks = []
                if hasattr(result, "blocks"):
                    for block in result.blocks:
                        if hasattr(block, "text"):
                            text_blocks.append(block.text)
                text = "\n".join(text_blocks)

            # 一時ファイル削除
            Path(temp_path).unlink(missing_ok=True)

            if text:
                logger.info(f"OCR完了: {filename}, 文字数={len(text)}")
            return text

        except Exception as e:
            logger.error(f"OCRエラー: {filename} - {e}")
            return None

    async def process_attachment(
        self,
        url: str,
        filename: str,
        content_type: str,
    ) -> str | None:
        """添付ファイルを処理してテキストを抽出"""
        if not self.is_image(content_type):
            logger.debug(f"画像以外はスキップ: {filename} ({content_type})")
            return None

        if not self.is_available():
            return None

        # ダウンロード
        image_data = await self.download_file(url)
        if not image_data:
            return None

        # OCR
        return await self.extract_text(image_data, filename)


# シングルトンインスタンス
ocr_processor = OCRProcessor()
