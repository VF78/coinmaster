"""Only M1 harness source-seal/JSON/retained-context proofs, no engines."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import hashlib,json,ast
from run_method_a_m1 import prepare,source_seal,verify_source,write_json,domain_context


def proof():
    prepared=prepare()
    assert prepared['recipe_sha256']=='c8a59ef0e962ac16ecb4c9fecd5fd469d0b52ee9261749dedc1868c4222e131c'
    assert prepared['config']['sha256']=='eb5ec0cee0ae1d8abc2eb33b1ab79ab44139f89630118692431f82670d1f0ee1'
    assert prepared['native_input_sha256']=='60825887adabf5c15b70f5e92854414d6e7f4d23759b667c5e0616aa6ae2dd51'
    with TemporaryDirectory(prefix='method-a-harness-pure-') as directory:
        root=Path(directory);(root/'runtime/coinmaster').mkdir(parents=True)
        (root/'runtime/tests').mkdir();code=root/'runtime/coinmaster/unit.py';code.write_text('VALUE=1'+chr(10))
        (root/'runtime/tests/unit.py').write_text('VALUE=2'+chr(10))
        source='a'*40;seal=source_seal(source,root);seal_path=root/'SOURCE_SEAL.json';write_json(seal_path,seal)
        gate=dict(source_commit=source,source_seal_path=str(seal_path),source_seal_sha256=hashlib.sha256(seal_path.read_bytes()).hexdigest())
        assert verify_source(gate,root)==source
        code.write_text('VALUE=3'+chr(10))
        try:verify_source(gate,root)
        except AssertionError:pass
        else:raise AssertionError('CHANGED_FROZEN_BYTES_ACCEPTED')
        path=root/'AFTER_DISPOSE.json';write_json(path,{'trader':{'disposed':True}})
        assert path.read_bytes().endswith(bytes([10])) and json.loads(path.read_text())=={'trader':{'disposed':True}}
    ep=NS(id='historical-alpha',btc_open_qty=0,sol_qty=0,pending={})
    context=domain_context(NS(_domain=NS(episode=ep),_pending_by_order={}))
    assert context['retained_episode_id']=='historical-alpha' and not context['owned_native_pending']
    tree=ast.parse(Path(__file__).with_name('run_method_a_m1.py').read_text())
    assert len([n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='BacktestEngine'])==1
    return dict(status='M1_HARNESS_PURE_PASS',engine_constructors=0,immutable_source_seal_verified=True,tampered_frozen_copy_rejected=True,
        JSON_actual_newline_and_roundtrip=True,retained_alpha_context_recorded_without_domain_reset=True,
        recipe_config_input_hashes_unchanged=True,planned_constructors=1)
