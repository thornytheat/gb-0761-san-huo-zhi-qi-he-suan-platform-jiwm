from app.pipeline import evaluate


def ledger(sources):
    return evaluate(sources)['ledger']


def test_dirty_price_and_bill(dirty):
    result = ledger(dirty)
    assert (result['expected_usd'], result['seen_invoice_usd'], result['delta_usd']) == ('160.00', '155.00', '5.00')
    assert result['rows'][1]['invoice_line'] == 3


def test_clean_has_two_zero_brackets(clean):
    assert [r['code'] for r in ledger(clean)['rows']] == ['MATCH', 'MATCH']


def test_missing_invoice_is_unknown_not_zero(dirty):
    dirty['invoice'] = 'tier,minutes,usd\n1,20,60\n'
    result = ledger(dirty)
    assert result['delta_usd'] is None and result['rows'][1]['code'] == 'INVOICE_MISSING'


def test_conflicting_bill_keeps_both_lines(dirty):
    dirty['invoice'] += '2,20,100\n'
    result = ledger(dirty)
    assert result['rows'][1]['conflict_lines'] == [3, 4]
    assert result['rows'][1]['code'] == 'INVOICE_CONFLICT'


def test_equal_money_different_minutes_is_disputed(dirty):
    dirty['invoice'] = dirty['invoice'].replace('19,95', '19,100')
    result = ledger(dirty)
    assert (result['delta_usd'], result['differences']) == ('0.00', 1)


def test_decimal_cents_without_float(dirty):
    dirty['terms'] = dirty['terms'].replace(',20,3,5', ',20,0.17,0.12')
    assert ledger(dirty)['expected_usd'] == '5.80'


def _despatch(dirty):
    dirty['terms'] = dirty['terms'].replace(',20,30,35,', ',20,30,100,')
    return dirty


def _undetermined(dirty):
    dirty['terms'] = dirty['terms'].replace(',20,30,35,', ',20,30,80,')
    return dirty


def test_confirmed_demurrage_is_direction_and_amount(dirty):
    result = ledger(dirty)
    assert (result['direction'], result['direction_settled'], result['confirmable_usd']) == ('DEMURRAGE', True, '160.00')
    assert result['confirmed_minutes'] == 40
    assert result['pending']['minutes'] == 15
    assert result['reversal']['required'] is False


def test_gap_keeps_amount_pending_not_confirmed(dirty):
    result = ledger(dirty)
    assert result['pending']['demurrage_usd'] == '75.00'
    assert result['pending']['demurrage_total_usd'] == '235.00'
    assert result['pending']['at_risk_usd'] == '75.00'


def test_direction_undetermined_when_gap_can_flip(dirty):
    result = ledger(_undetermined(dirty))
    assert (result['direction'], result['direction_settled']) == ('UNDETERMINED', False)
    assert result['confirmable_usd'] is None
    assert result['pending']['demurrage_total_usd'] == '30.00'
    assert result['pending']['despatch_total_usd'] == '7.50'


def test_despatch_uses_half_of_first_tier(dirty):
    result = ledger(_despatch(dirty))
    assert (result['direction'], result['despatch']['rate_usd_min']) == ('DESPATCH', '1.50')
    assert result['confirmable_usd'] == '15.00'
    assert result['confirmed_minutes'] == 10


def test_despatch_reverses_ship_invoice_not_zero(dirty):
    result = ledger(_despatch(dirty))
    assert result['reversal'] == {'required': True, 'pending': False, 'invoice_usd': '155.00',
                                  'usd': '-155.00', 'reason': 'OPPOSITE_DIRECTION'}
    assert result['delta_usd'] == '-155.00'


def test_undetermined_holds_reversal(dirty):
    result = ledger(_undetermined(dirty))
    assert result['reversal']['required'] is False and result['reversal']['pending'] is True
    assert result['reversal']['reason'] == 'DIRECTION_UNSETTLED'
    assert result['delta_usd'] is None


def test_balance_reverses_invoice_as_no_liability(clean):
    clean['invoice'] = 'tier,minutes,usd\n1,5,15\n2,0,0\n'
    result = ledger(clean)
    assert (result['direction'], result['reversal']['required']) == ('BALANCED', True)
    assert result['reversal']['usd'] == '-15.00'


def test_incomplete_invoice_holds_reversal(dirty):
    # The reversal is only at stake once the run is not demurrage; with the
    # invoice missing a tier its full amount (and so the reversal) is unknown.
    result = ledger(_despatch(dirty) | {'invoice': 'tier,minutes,usd\n1,20,155\n'})
    assert result['reversal']['pending'] is True and result['reversal']['required'] is False
    assert result['reversal']['reason'] == 'INVOICE_INCOMPLETE'
    assert result['delta_usd'] is None

