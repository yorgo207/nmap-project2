from flask import Flask, request, jsonify
import os
import datetime
from dotenv import load_dotenv
from nmap_automator.interpretors import InterpretorFactory
from nmap_automator.scanner import NmapScanner
from nmap_automator.config_loader import Config, NmapScanRequest, LLMInterpretRequest, ScannerConfig, InterpretorConfig, SubdomainRequest
from nmap_automator.utils.api_utils import parse_request_data, read_results_from_csv
from pydantic import ValidationError

api_server = Flask(__name__)

class Runner:
    def __init__(self):
        load_dotenv()

    def _create_interpretor(self, conf: InterpretorConfig):
        api_key = None
        if conf.interpretor_type == "gpt":
            api_key = os.getenv("OPENAI_API_KEY")
        elif conf.interpretor_type == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")

        interpretor = InterpretorFactory.create_interpretor(
          conf.interpretor_type,
          "Nmap Automator",
          conf.model_flavor,
          api_key=api_key
        )
        interpretor.configure()
        return interpretor
    
    def create_save_dir(self, scanner_conf: ScannerConfig) -> str:
        scan_name = f"scan_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        full_path = os.path.join(scanner_conf.save_dir, scan_name)
        os.makedirs(full_path, exist_ok=True)
        return full_path

    def scan_with_nmap(self, scanner_conf: ScannerConfig, target: str, scan_dir: str) -> dict:
        """
        Perform an Nmap scan for a single target.

        :param scanner_conf: ScannerConfig object with nmap_args and save_dir.
        :param target: The specific target to scan (single IP or hostname).
        :return: Dictionary containing scan results and metadata.
        """
        scanner = NmapScanner()
        nmap_args = " ".join(scanner_conf.nmap_args)

        try:
            print(f"Scanning target: {target} with args: {nmap_args}")
            scan_results = scanner.scan(
                target=target,
                arguments=nmap_args,
                save_dir=scan_dir
            )
            return {
                "target": target,
                "results": scan_results,
                "nmap_args": scanner_conf.nmap_args
            }
        except Exception as e:
            print(f"Error scanning target {target}: {e}")
            return {
                "target": target,
                "error": str(e),
                "nmap_args": scanner_conf.nmap_args
            }
    
    def run_llm_interpretation(self, interpreter_conf: InterpretorConfig, results: list[dict], save_dir: str) -> list[dict]:
        interpretor = self._create_interpretor(interpreter_conf)
        print("Interpreting with", interpreter_conf.interpretor_type, " via ", interpreter_conf.model_flavor)
        runner_type = interpreter_conf.interpret_runner
        if runner_type == "normal":
            res = interpretor.interpret(results, save_dir)
        elif runner_type == "restricted":
            res = interpretor.interpret_restricted(results, save_dir)
        elif runner_type == "suggest":
            res = interpretor.interpret_with_suggestions(results, save_dir)
        else:
            raise Exception(f"Invalid interpret_runner: {runner_type}")
        
        return res

    def process_scan(self, conf: Config):
        save_dir = self.create_save_dir(conf.scanner)
        nmap_results = self.scan_with_nmap(scanner_conf=conf.scanner, save_dir=save_dir)
        interpreter_results = self.run_llm_interpretation(interpreter_conf=conf.interpretor, results=nmap_results, save_dir=save_dir)
        return interpreter_results, nmap_results
    
def scan():
    """Combined operation: Nmap scan + LLM interpretation."""
    conf, error_response = parse_request_data()
    if error_response:
        return error_response

    try:
        runner = Runner()
        interpreted_results, raw_results = runner.process_scan(conf)
        return jsonify({
            "raw_results": raw_results,
            "interpreted_results": interpreted_results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def nmap_scan():
    """Run only the Nmap scan."""
    try:
        # Parse request payload
        data = request.get_json()
        print(f"Received payload: {data}")

        request_model = NmapScanRequest(**data)
        scanner_config = request_model.scanner

        # Initialize runner
        runner = Runner()

        # Create a save directory for the scan
        scan_dir = runner.create_save_dir(scanner_conf=scanner_config)

        # Run the scan for all targets
        all_results = []
        for target in scanner_config.target:
            scan_result = runner.scan_with_nmap(scanner_conf=scanner_config, target=target, scan_dir=scan_dir)
            all_results.append(scan_result)

        return jsonify({
            "data": all_results,
            "scan_file_path": os.path.join(scan_dir, "initial_scan_results.csv"),
            "scan_dir_path": scan_dir
        })
    except ValidationError as e:
        print(f"Validation Error: {e}")
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        print(f"Unhandled Exception: {e}")
        return jsonify({"error": str(e)}), 500



def llm_interpret():
    """Run only the LLM interpretation on provided scan results."""
    try:
        data = request.get_json()
        request_model = LLMInterpretRequest(**data)  # Validate request

        # Validate and extract configurations
        # conf = Config(scanner=request_model.scanner, interpretor=request_model.interpretor)
        conf = request_model.interpretor
        raw_results = read_results_from_csv(request_model.scan_file_path)

        runner = Runner()
        interpreted_results = runner.run_llm_interpretation(conf, raw_results, request_model.scan_dir_path)
        return jsonify({
            "interpreted_results": interpreted_results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def enumerate_subdomains():
    """Dummy function to return hardcoded subdomains for megacorpone.com."""
    try:
        data = request.get_json()
        request_model = SubdomainRequest(**data)  # Validate request with Pydantic

        if request_model.domain != "megacorpone.com":
            return jsonify({"error": "This function only supports megacorpone.com."}), 400

        # Hardcoded list of subdomains for megacorpone.com
        # tried using sublist3r -> kouuusa
        subdomains = [
            "www.megacorpone.com",
            "admin.megacorpone.com",
            "mail.megacorpone.com",
            "vpn.megacorpone.com",
            "test.megacorpone.com",
            "beta.megacorpone.com",
            "fs1.megacorpone.com",
            "intranet.megacorpone.com",
            "mail2.megacorpone.com",
            "ns1.megacorpone.com",
            "ns2.megacorpone.com",
            "ns3.megacorpone.com",
            "router.megacorpone.com",
            "siem.megacorpone.com",
            "snmp.megacorpone.com",
            "support.megacorpone.com",
            "syslog.megacorpone.com",
            "test.megacorpone.com",
        ]

        return jsonify({"domain": request_model.domain, "subdomains": subdomains})
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



def create_api_server() -> Flask:
    api_server = Flask(__name__)
    api_server.add_url_rule('/scan', 'scan', scan, methods=['POST'])
    api_server.add_url_rule('/nmap_scan', 'nmap_scan', nmap_scan, methods=['POST'])
    api_server.add_url_rule('/llm_interpret', 'llm_interpret', llm_interpret, methods=['POST'])
    api_server.add_url_rule('/enumerate_subdomains', 'enumerate_subdomains', enumerate_subdomains, methods=['POST'])
    return api_server