// Existing domain service, exact signed synthetic database; never raw-row seeding.
import {spawnSync} from 'node:child_process';
export function prepareReadOnlyRecommendation(token,campaignId) {
 if(!/^[a-f0-9]{16}$/.test(token) || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(campaignId)) throw Error('EXACT_QA_IDENTITY_REQUIRED');
 const code=String.raw`
import json, os, sys, uuid
try:
 from qa.postgres_instance import QaInstance, database_name
 instance=QaInstance(); instance.verify_server(); record=instance.load(sys.argv[1])
 if record['state'] != 'ACTIVE': raise ValueError('ACTIVE_QA_REQUIRED')
 from sqlalchemy.engine import make_url
 url=make_url(os.environ['QA_DATABASE_ADMIN_URL']).set(database=database_name(sys.argv[1]))
 for key in list(os.environ):
  if key.startswith('VAYUJIT_') or key in {'OPENAI_API_KEY','WORDPRESS_APPLICATION_PASSWORD'}: del os.environ[key]
 os.environ.update(VAYUJIT_ENV='test',VAYUJIT_ENVIRONMENT='test',VAYUJIT_DATABASE_URL=url.render_as_string(hide_password=False))
 from vayujit_api.core.config import Settings
 Settings.model_config['env_file']=None
 from vayujit_api.main import app
 from vayujit_api.core.database import SessionFactory
 from vayujit_api.core.test_database import assert_safe_test_database
 from vayujit_api.ads.models import AdCampaign, AdAccount
 from vayujit_api.ads.optimization import create_recommendation
 from vayujit_api.identity.models import User
 from sqlalchemy import select
 with SessionFactory() as db:
  assert_safe_test_database(db.connection(),database_url=str(url),environment='test')
  owner=db.scalar(select(User))
  campaign=db.get(AdCampaign,uuid.UUID(sys.argv[2]))
  account=db.get(AdAccount,campaign.account_id) if campaign else None
  if not owner or owner.email != 'qa-wp3@example.com' or not campaign or campaign.owner_id != owner.id or not campaign.name.startswith('[QA SYNTHETIC] WP7A2 WP7B') or campaign.remote_campaign_id or campaign.provider != 'meta' or not account or account.environment != 'local': raise ValueError('EXACT_LOCAL_UNPUBLISHED_FIXTURE_REQUIRED')
  row=create_recommendation(db,owner,campaign,'review_destination',{'issue':'[QA SYNTHETIC] accessibility-only read-only preview fixture','fixture_only':True},confidence='low')
  db.commit()
  print(json.dumps({'id':str(row.id),'source':row.source,'synthetic':True,'remote_execution':False}))
except Exception:
 print(json.dumps({'status':'BLOCKED','raw_error_persisted':False})); sys.exit(1)
`;
 const r=spawnSync('apps/api/.venv/Scripts/python.exe',['-c',code,token,campaignId],{encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:1024*1024});
 if(r.status!==0) throw Error('CANONICAL_READ_ONLY_RECOMMENDATION_FIXTURE_FAILED');
 const value=JSON.parse(r.stdout.trim().split(/\r?\n/).at(-1));
 if(value.synthetic!==true || value.remote_execution!==false) throw Error('SYNTHETIC_DOMAIN_RESULT_REQUIRED');
 return value;
}
