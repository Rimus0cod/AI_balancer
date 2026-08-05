import argparse
from src.ai_balancer.ingestion.opendota import OpenDotaClient, looks_like_ranked
from src.ai_balancer.processing.transformer import validate_and_report
from src.ai_balancer.storage.local import LocalStorage

def main():
    parser = argparse.ArgumentParser(description="AI Balancer Ingestion CLI")
    parser.add_argument("match_ids", type=int, nargs="+", help="Dota 2 Match IDs to ingest")
    args = parser.parse_args()

    client = OpenDotaClient()
    storage = LocalStorage()

    for match_id in args.match_ids:
        print(f"--- Processing Match ID: {match_id} ---")
        try:
            # 1. Fetch
            raw_data, provenance = client.fetch_match(match_id)
            print("Successfully fetched from OpenDota.")

            # 2. Store Raw
            raw_path = storage.save_raw(match_id, raw_data, provenance)
            print(f"Raw data saved to {raw_path}")

            # 3. Process & Validate
            match_obj, report = validate_and_report(raw_data)

            if match_obj and looks_like_ranked(raw_data):
                # 4. Store Processed
                proc_path = storage.save_processed_ranked(match_id, match_obj)
                print(f"Validation {report}")
                print(f"Processed data saved to {proc_path}")
            elif match_obj:
                proc_path = storage.save_processed_filtered(match_id, match_obj)
                print(f"Validation {report}")
                print(f"Match failed ranked filters; processed data saved to {proc_path}")
            else:
                print(f"Validation {report}")
                print("Skipping processed storage due to validation failure.")

        except Exception as e:
            print(f"Error processing match {match_id}: {e}")

if __name__ == "__main__":
    main()
