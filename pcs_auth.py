import yaml
import requests

def auth():
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    client_id = config["pcs"]["ClientId"]
    redirect_url = config["pcs"]["RedirectUrl"]
    secret_key = config["pcs"]["SecretKey"]

    code_url = (
        "https://openapi.baidu.com/oauth/2.0/authorize?"
        "response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_url}&"
        f"scope=basic,netdisk&"
        "display=page"
    )

    auth_code = input(f"授权地址：{code_url}\n请访问授权地址获取授权码，并粘贴到控制台，粘贴后按回车键结束...\n")

    auth_url = (
        "https://openapi.baidu.com/oauth/2.0/token?"
        "grant_type=authorization_code&"
        f"code={auth_code}&"
        f"client_id={client_id}&"
        f"client_secret={secret_key}&"
        f"redirect_uri={redirect_url}"
    )

    response = requests.get(auth_url).json()

    return response["access_token"]

if __name__ == "__main__":
    token = auth()
    print(token)