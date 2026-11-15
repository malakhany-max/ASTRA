import sqlite3
import astra_security as sec


def _ok(res):
    return res if isinstance(res, bool) else bool(res[0])


def test_chain_valid_then_detects_tamper():
    for i in range(5):
        sec.audit_log("admin", "login", f"user{i}", {"i": i})
    assert _ok(sec.verify_chain())

    con = sqlite3.connect(sec.db_path())
    tbl = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' and name like '%audit%'")][0]
    con.execute(f"update {tbl} set action='hacked' where rowid=2")
    con.commit()
    con.close()
    assert not _ok(sec.verify_chain())
