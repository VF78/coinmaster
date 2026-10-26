"""Bounded read-only public native account facts; no account export/PnL/guards."""
def native_account_snapshot(account,instruments):
    errors=[]
    result=dict(status="UNKNOWN",complete=False,errors=errors,instruments={})
    def error(field,exc):
        try:message=str(exc)
        except Exception:message="<unprintable native getter error>"
        errors.append(dict(field=field,type=type(exc).__name__,message=message))
    def query(field,getter,encode=lambda value:value):
        try:return encode(getter())
        except Exception as exc:error(field,exc);return "UNKNOWN"
    def money(value):
        if value is None:return dict(status="ABSENT_NATIVE_VALUE")
        amount=value.as_decimal()
        if not amount.is_finite():raise ValueError("nonfinite native Money")
        return dict(amount=str(amount),currency=str(value.currency),text=str(value))
    def money_map(values):return {str(key):money(value)for key,value in values.items()}
    def scalar(value):
        if value is None:return dict(status="ABSENT_NATIVE_VALUE")
        if hasattr(value,"is_finite")and not value.is_finite():raise ValueError("nonfinite native scalar")
        return str(value)
    if account is None:
        errors.append(dict(field="account",type="MissingNativeAccount",message="Native cache account absent"))
        return result
    result["id"]=query("id",lambda:account.id,str)
    result["type"]=query("type",lambda:account.type,lambda value:str(getattr(value,"name",value)))
    result["base_currency"]=query("base_currency",lambda:account.base_currency,lambda value:None if value is None else str(value))
    result["default_leverage"]=query("default_leverage",lambda:account.default_leverage,scalar)
    for name in("balances_total","balances_free","balances_locked","commissions"):
        result[name]=query(name,lambda name=name:getattr(account,name)(),money_map)
    for instrument in instruments:
        key=str(instrument)
        result["instruments"][key]=dict(
            margin_init=query(key+".margin_init",lambda instrument=instrument:account.margin_init(instrument),money),
            margin_maint=query(key+".margin_maint",lambda instrument=instrument:account.margin_maint(instrument),money),
            leverage=query(key+".leverage",lambda instrument=instrument:account.leverage(instrument),scalar))
    result["complete"]=not errors
    result["status"]="KNOWN"if result["complete"]else"UNKNOWN"
    return result
