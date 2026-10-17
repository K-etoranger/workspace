"""sb: SecondBrain への唯一の書き込み口。"""

VERSION = "1.0.0"
FORMAT = 1


class SbError(Exception):
    """終了コードつきの誤り。0 成功 / 1 形の誤り / 2 ロック / 3 対象なし / 4 書き込み拒否 / 5 内部。"""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
