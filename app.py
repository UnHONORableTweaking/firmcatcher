from flask import Flask, render_template, request, jsonify
import requests
import json

devCert=""
devSN=""

app = Flask(__name__)

# Function to read regions.txt and create a dictionary
def load_regions():
    regions = {}
    try:
        with open("regions.txt", "r") as file:
            for line in file:
                if ":" in line:
                    region, vendor_country = line.strip().split(":")
                    regions[region] = vendor_country
    except FileNotFoundError:
        print("regions.txt not found. VendorCountry and Region fields will not work.")
    return regions

# Load regions into a dictionary
regions_dict = load_regions()

# Function to parse the Full FW identifier
def parse_fw_identifier(full_fw):
    parts = full_fw.split()
    if len(parts) < 2:
        return None, None, None, None, None, None, None, None

    fw_name = parts[0]
    fw_version = parts[1]

    # Extract prefix (e.g., DCO, VER, PGT) and components from the FW name
    fw_components = fw_name.split('-')
    if len(fw_components) < 3:
        return None, None, None, None, None, None, None, None

    prefix = fw_components[0]  # Extract prefix (e.g., DCO, VER, PGT)
    model = fw_components[1]
    project = fw_components[2]

    # Extract version and variant
    version_parts = fw_version.split('(')
    version = version_parts[0]
    variant = version_parts[1][:-1] if len(version_parts) > 1 else ""

    # Extract region, custversion, preloadsub, and patchver from the variant
    region = variant.split('E')[0]  # C185
    custversion = variant.split('E')[1].split('R')[0]  # 6
    preloadsub = variant.split('R')[1].split('P')[0]  # 5
    patchver = variant.split('P')[1]  # 3

    # Determine groupregion based on the number after LGRP in the project name
    if project.startswith("LGRP"):
        lgrp_number = int(project[4:])  # Extract the number after LGRP
        groupregion = "OVS" if lgrp_number % 2 == 0 else "CHN"
    else:
        groupregion = "UNKNOWN"  # Fallback if project doesn't start with LGRP

    # Generate Base, Cust, and Preload strings using the extracted components
    base = f"{prefix}-{project}-{groupregion} {version}"
    cust = f"{prefix}-{model}-CUST {version.split('.')[0]}.{version.split('.')[1]}.{version.split('.')[2]}.{custversion}({region})"
    preload = f"{prefix}-{model}-PRELOAD {version.split('.')[0]}.{version.split('.')[1]}.{version.split('.')[2]}.{patchver}({region}R{preloadsub})"
    full_model = f"{prefix}-{model}"

    # Get VendorCountry from regions_dict
    vendor_country = regions_dict.get(region, "Unknown")

    return base, cust, preload, full_model, region, vendor_country

# Function to get firmware from honor
def get_firmware_info(full_model, vendor_country, base, cust, preload):
    global devCert
    global devSN
    global keyAtt
    
    payload = {
        "commonRules": {
            "devModel": full_model,
            "plmn": "-",
            "subGroup": "",
            "updateAction": "recovery",
            "vendorCountry": vendor_country,
            "verGroup": ""
        },
        "cotaInfo": {
            "country": "DEFAULT",
            "vendorCota": "",
            "vendorExpiredTime": ""
        },
        "deviceCertificate": devCert,  # Add your certificate here
        "deviceInfo": {
            "deviceId": devSN
        },
        "keyAttestation": keyAtt,  # Add your key attestation here
        "versionPackageRules": [
            {
                "versionNumber": base,
                "versionPackageType": 2
            },
            {
                "versionNumber": cust,
                "versionPackageType": 3
            },
            {
                "versionNumber": preload,
                "versionPackageType": 4
            }
        ]
    }

    try:
        response = requests.post(
            "https://update.platform.hihonorcloud.com/blversion/v1/version/check",
            headers={
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Host": "update.platform.hihonorcloud.com",
                "Content-Type": "application/json;charset=UTF-8",
                "x-requestId": "-"
            },
            json=payload
        )
        response_json = response.json()

        # Extract the versionList from the response
        version_list = response_json.get("result", {}).get("versionList", [])
        formatted_lines = []

        for item in version_list:
            version_number = item.get("versionNumber", "")
            url = item.get("url", "")

            # Check if the versionNumber is numeric (e.g., "253950528")
            if version_number.isdigit():
                # Append "(Changelog)" and add "/changelog.xml" to the URL
                if not url.endswith("/"):
                    url += "/"
                changelog_url = f"{url}changelog.xml"
                formatted_line = f"{version_number} (Changelog): <a href='{changelog_url}'>{changelog_url}</a>"
            else:
                # Use the versionNumber and URL as-is
                formatted_line = f"{version_number}: <a href='{url}full/filelist.xml'>{url}</a>"

            formatted_lines.append(formatted_line)

        # Join all lines into a single string
        formatted_response = "<br>".join(formatted_lines)
        return formatted_response
    except Exception as e:
        return f"Error: {str(e)}"

# Home route
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        full_fw = request.form.get("full_fw")
        base, cust, preload, full_model, region, vendor_country = parse_fw_identifier(full_fw)
        if base and cust and preload:
            firmware_info = get_firmware_info(full_model, vendor_country, base, cust, preload)
            return render_template("index.html", 
                                 base=base, cust=cust, preload=preload, 
                                 region=region, vendor_country=vendor_country, 
                                 firmware_info=firmware_info)
        else:
            return render_template("index.html", error="Invalid Full FW Identifier")
    return render_template("index.html")

# Run the app
if __name__ == "__main__":
    app.run(debug=True,port=8189)
