import sys
import time
import requests
import json
import os
from antlr4 import *
from TerraformSubsetLexer import TerraformSubsetLexer
from TerraformSubsetParser import TerraformSubsetParser
from TerraformSubsetListener import TerraformSubsetListener

class TerraformApplyListener(TerraformSubsetListener):
    def __init__(self):
        self.variables = {}
        self.provider_token_expr = None
        self.droplet_config = {}

    def enterVariable(self, ctx):
        var_name = ctx.STRING().getText().strip('"')
        for kv in ctx.body().keyValue():
            key = kv.IDENTIFIER().getText()
            if key == "default":
                value = kv.expr().getText().strip('"')
                self.variables[var_name] = value
                print(f"[var] {var_name} = {value}")

    def enterProvider(self, ctx):
        provider_name = ctx.STRING().getText().strip('"')
        if provider_name != "digitalocean":
            raise Exception("Only 'digitalocean' provider is supported.")
        for kv in ctx.body().keyValue():
            key = kv.IDENTIFIER().getText()
            expr = kv.expr().getText()
            if key == "token":
                self.provider_token_expr = expr

    def enterResource(self, ctx):
        type_ = ctx.STRING(0).getText().strip('"')
        name = ctx.STRING(1).getText().strip('"')
        if type_ != "digitalocean_droplet":
            return
        for kv in ctx.body().keyValue():
            key = kv.IDENTIFIER().getText()
            val = kv.expr().getText().strip('"')
            self.droplet_config[key] = val

    def resolve_token(self):
        if not self.provider_token_expr:
            raise Exception("No token specified in provider block.")
        if self.provider_token_expr.startswith("var."):
            var_name = self.provider_token_expr.split(".")[1]
            if var_name in self.variables:
                return self.variables[var_name]
            else:
                raise Exception(f"Undefined variable '{var_name}' used in provider block.")
        return self.provider_token_expr.strip('"')

def create_droplet(api_token, config):
    url = "https://api.digitalocean.com/v2/droplets"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    payload = {
        "name": config["name"],
        "region": config["region"],
        "size": config["size"],
        "image": config["image"],
        "ssh_keys": [],
        "backups": False,
        "ipv6": False,
        "user_data": None,
        "private_networking": None,
        "volumes": None,
        "tags": []
    }
    print("[*] Creating droplet...")
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    droplet = response.json()["droplet"]
    droplet_id = droplet["id"]
    print(f"[+] Droplet created with ID: {droplet_id}")
    
    print("[*] Waiting for droplet to become active and assigned an IP...")
    while True:
        resp = requests.get(f"https://api.digitalocean.com/v2/droplets/{droplet_id}", headers=headers)
        droplet_info = resp.json()["droplet"]
        networks = droplet_info["networks"]["v4"]
        public_ips = [n["ip_address"] for n in networks if n["type"] == "public"]
        if public_ips:
            ip = public_ips[0]
            save_state(config["name"], droplet_id, ip)
            return ip
        time.sleep(5)

def destroy_droplet(api_token, droplet_name):
    state_file = f"{droplet_name}.tfstate"
    
    if not os.path.exists(state_file):
        print(f"[!] State file {state_file} not found. Cannot destroy droplet.")
        return
    
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        droplet_id = state["droplet_id"]
        ip = state["ip"]
        
        print(f"[*] Found droplet ID {droplet_id} with IP {ip} in state file")
        print("[*] Destroying droplet...")
        
        url = f"https://api.digitalocean.com/v2/droplets/{droplet_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }
        
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        
        print(f"[✓] Droplet {droplet_id} destroyed successfully")
        
        os.remove(state_file)
        print(f"[✓] State file {state_file} removed")
        
    except json.JSONDecodeError:
        print(f"[!] Error reading state file {state_file}")
    except requests.exceptions.RequestException as e:
        print(f"[!] Error destroying droplet: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")

def save_state(droplet_name, droplet_id, ip):
    state_file = f"{droplet_name}.tfstate"
    state = {
        "droplet_id": droplet_id,
        "ip": ip,
        "name": droplet_name
    }
    
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"[✓] State saved to {state_file}")

def terraform_apply(terraform_file):
    input_stream = FileStream(terraform_file)
    lexer = TerraformSubsetLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = TerraformSubsetParser(stream)
    tree = parser.terraform()

    listener = TerraformApplyListener()
    walker = ParseTreeWalker()
    walker.walk(listener, tree)

    token = listener.resolve_token()
    if not listener.droplet_config:
        raise Exception("Missing digitalocean_droplet resource.")

    ip = create_droplet(token, listener.droplet_config)
    print(f"[✓] Droplet available at IP: {ip}")

def terraform_destroy(terraform_file):
    input_stream = FileStream(terraform_file)
    lexer = TerraformSubsetLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = TerraformSubsetParser(stream)
    tree = parser.terraform()

    listener = TerraformApplyListener()
    walker = ParseTreeWalker()
    walker.walk(listener, tree)

    token = listener.resolve_token()
    if not listener.droplet_config:
        raise Exception("Missing digitalocean_droplet resource.")

    droplet_name = listener.droplet_config["name"]
    destroy_droplet(token, droplet_name)

def main(argv):
    if len(argv) < 2:
        print("Usage: python script.py <terraform_file> [--auto-approve]")
        sys.exit(1)
    
    terraform_file = argv[1]
    auto_approve = "--auto-approve" in argv
    
    if "--destroy" in argv or any("destroy" in arg for arg in argv):
        if auto_approve:
            terraform_destroy(terraform_file)
        else:
            confirm = input("Do you really want to destroy all resources? (yes/no): ")
            if confirm.lower() == "yes":
                terraform_destroy(terraform_file)
            else:
                print("Destroy cancelled.")
    else:
        terraform_apply(terraform_file)

if __name__ == "__main__":
    main(sys.argv)
