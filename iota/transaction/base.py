# coding=utf-8
from __future__ import absolute_import, division, print_function, \
  unicode_literals

from operator import attrgetter
from typing import Iterable, Iterator, List, MutableSequence, \
  Optional, Sequence, Text

from iota.codecs import TrytesDecodeError
from iota.crypto import Curl, HASH_LENGTH
from iota.json import JsonSerializable
from iota.transaction.types import BundleHash, Fragment, Nonce, \
  TransactionHash, TransactionTrytes
from iota.trits import int_from_trits, trits_from_int
from iota.types import Address, Tag, TryteString, TrytesCompatible

__all__ = [
  'Bundle',
  'Transaction',
]


class Transaction(JsonSerializable):
  """
  A transaction that has been attached to the Tangle.
  """
  @classmethod
  def from_tryte_string(cls, trytes, hash_=None):
    # type: (TrytesCompatible, Optional[TransactionHash]) -> Transaction
    """
    Creates a Transaction object from a sequence of trytes.

    :param trytes:
      Raw trytes.  Should be exactly 2673 trytes long.

    :param hash_:
      The transaction hash, if available.
      If not provided, it will be computed from the transaction trytes.
    """
    tryte_string = TransactionTrytes(trytes)

    if not hash_:
      hash_trits = [0] * HASH_LENGTH # type: MutableSequence[int]

      sponge = Curl()
      sponge.absorb(tryte_string.as_trits())
      sponge.squeeze(hash_trits)

      hash_ = TransactionHash.from_trits(hash_trits)

    return cls(
      hash_ = hash_,
      signature_message_fragment = Fragment(tryte_string[0:2187]),
      address = Address(tryte_string[2187:2268]),
      value = int_from_trits(tryte_string[2268:2295].as_trits()),
      legacy_tag = Tag(tryte_string[2295:2322]),
      timestamp = int_from_trits(tryte_string[2322:2331].as_trits()),
      current_index = int_from_trits(tryte_string[2331:2340].as_trits()),
      last_index = int_from_trits(tryte_string[2340:2349].as_trits()),
      bundle_hash = BundleHash(tryte_string[2349:2430]),
      trunk_transaction_hash = TransactionHash(tryte_string[2430:2511]),
      branch_transaction_hash = TransactionHash(tryte_string[2511:2592]),
      tag = Tag(tryte_string[2592:2619]),
      attachment_timestamp = int_from_trits(tryte_string[2619:2628].as_trits()),
      attachment_timestamp_lower_bound = int_from_trits(tryte_string[2628:2637].as_trits()),
      attachment_timestamp_upper_bound = int_from_trits(tryte_string[2637:2646].as_trits()),
      nonce = Nonce(tryte_string[2646:2673]),
    )

  def __init__(
      self,
      hash_,                            # type: Optional[TransactionHash]
      signature_message_fragment,       # type: Optional[Fragment]
      address,                          # type: Address
      value,                            # type: int
      timestamp,                        # type: int
      current_index,                    # type: Optional[int]
      last_index,                       # type: Optional[int]
      bundle_hash,                      # type: Optional[BundleHash]
      trunk_transaction_hash,           # type: Optional[TransactionHash]
      branch_transaction_hash,          # type: Optional[TransactionHash]
      tag,                              # type: Optional[Tag]
      attachment_timestamp,             # type: Optional[int]
      attachment_timestamp_lower_bound, # type: Optional[int]
      attachment_timestamp_upper_bound, # type: Optional[int]
      nonce,                            # type: Optional[Nonce]
      legacy_tag = None                 # type: Optional[Tag]
  ):
    self.hash = hash_
    """
    Transaction ID, generated by taking a hash of the transaction
    trits.
    """

    self.bundle_hash = bundle_hash
    """
    Bundle hash, generated by taking a hash of metadata from all the
    transactions in the bundle.
    """

    self.address = address
    """
    The address associated with this transaction.
    If ``value`` is != 0, the associated address' balance is adjusted
    as a result of this transaction.
    """

    self.value = value
    """
    Amount to adjust the balance of ``address``.
    Can be negative (i.e., for spending inputs).
    """

    self._legacy_tag = legacy_tag
    """
    Optional classification legacy_tag applied to this transaction.
    """

    self.nonce = nonce
    """
    Unique value used to increase security of the transaction hash.
    """

    self.timestamp = timestamp
    """
    Timestamp used to increase the security of the transaction hash.

    IMPORTANT: This value is easy to forge!
    Do not rely on it when resolving conflicts!
    """

    self.current_index = current_index
    """
    The position of the transaction inside the bundle.

    For value transfers, the "spend" transaction is generally in the
    0th position, followed by inputs, and the "change" transaction is
    last.
    """

    self.last_index = last_index
    """
    The position of the final transaction inside the bundle.
    """

    self.trunk_transaction_hash = trunk_transaction_hash
    """
    In order to add a transaction to the Tangle, you must perform PoW
    to "approve" two existing transactions, called the "trunk" and
    "branch" transactions.

    The trunk transaction is generally used to link transactions within
    a bundle.
    """

    self.branch_transaction_hash = branch_transaction_hash
    """
    In order to add a transaction to the Tangle, you must perform PoW
    to "approve" two existing transactions, called the "trunk" and
    "branch" transactions.

    The branch transaction generally has no significance.
    """

    self.tag = tag
    """
    Optional classification tag applied to this transaction.
    """

    self.attachment_timestamp = attachment_timestamp

    self.attachment_timestamp_lower_bound = attachment_timestamp_lower_bound

    self.attachment_timestamp_upper_bound = attachment_timestamp_upper_bound

    self.signature_message_fragment = signature_message_fragment
    """
    "Signature/Message Fragment" (note the slash):

    - For inputs, this contains a fragment of the cryptographic
      signature, used to verify the transaction (the entire signature
      is too large to fit into a single transaction, so it is split
      across multiple transactions instead).

    - For other transactions, this contains a fragment of the message
      attached to the transaction (if any).  This can be pretty much
      any value.  Like signatures, the message may be split across
      multiple transactions if it is too large to fit inside a single
      transaction.
    """

    self.is_confirmed = None # type: Optional[bool]
    """
    Whether this transaction has been confirmed by neighbor nodes.
    Must be set manually via the ``getInclusionStates`` API command.

    References:
      - :py:meth:`iota.api.StrictIota.get_inclusion_states`
      - :py:meth:`iota.api.Iota.get_transfers`
    """

  @property
  def is_tail(self):
    # type: () -> bool
    """
    Returns whether this transaction is a tail.
    """
    return self.current_index == 0

  @property
  def value_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's value.
    """
    # Note that we are padding to 81 _trits_.
    return TryteString.from_trits(trits_from_int(self.value, pad=81))

  @property
  def timestamp_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    timestamp.
    """
    # Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.timestamp, pad=27))

  @property
  def current_index_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    ``current_index`` value.
    """
    # Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.current_index, pad=27))

  @property
  def last_index_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    ``last_index`` value.
    """
    # Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.last_index, pad=27))

  @property
  def attachment_timestamp_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    attachment timestamp.
    """
    #Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.attachment_timestamp, pad=27))

  @property
  def attachment_timestamp_lower_bound_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    attachment timestamp lower bound.
    """
    #Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.attachment_timestamp_lower_bound, pad=27))

  @property
  def attachment_timestamp_upper_bound_as_trytes(self):
    # type: () -> TryteString
    """
    Returns a TryteString representation of the transaction's
    attachment timestamp upper bound.
    """
    #Note that we are padding to 27 _trits_.
    return TryteString.from_trits(trits_from_int(self.attachment_timestamp_upper_bound, pad=27))

  def as_json_compatible(self):
    # type: () -> dict
    """
    Returns a JSON-compatible representation of the object.

    References:
      - :py:class:`iota.json.JsonEncoder`.
    """
    return {
      'hash_':                              self.hash,
      'signature_message_fragment':         self.signature_message_fragment,
      'address':                            self.address,
      'value':                              self.value,
      'legacy_tag':                         self.legacy_tag,
      'timestamp':                          self.timestamp,
      'current_index':                      self.current_index,
      'last_index':                         self.last_index,
      'bundle_hash':                        self.bundle_hash,
      'trunk_transaction_hash':             self.trunk_transaction_hash,
      'branch_transaction_hash':            self.branch_transaction_hash,
      'tag':                                self.tag,
      'attachment_timestamp':               self.attachment_timestamp,
      'attachment_timestamp_lower_bound':   self.attachment_timestamp_lower_bound,
      'attachment_timestamp_upper_bound':   self.attachment_timestamp_upper_bound,
      'nonce':                              self.nonce,
    }

  def as_tryte_string(self):
    # type: () -> TransactionTrytes
    """
    Returns a TryteString representation of the transaction.
    """
    return TransactionTrytes(
        self.signature_message_fragment
      + self.address.address
      + self.value_as_trytes
      + self.legacy_tag
      + self.timestamp_as_trytes
      + self.current_index_as_trytes
      + self.last_index_as_trytes
      + self.bundle_hash
      + self.trunk_transaction_hash
      + self.branch_transaction_hash
      + self.tag
      + self.attachment_timestamp_as_trytes
      + self.attachment_timestamp_lower_bound_as_trytes
      + self.attachment_timestamp_upper_bound_as_trytes
      + self.nonce
    )

  def get_signature_validation_trytes(self):
    # type: () -> TryteString
    """
    Returns the values needed to validate the transaction's
    ``signature_message_fragment`` value.
    """
    return (
        self.address.address
      + self.value_as_trytes
      + self.legacy_tag
      + self.timestamp_as_trytes
      + self.current_index_as_trytes
      + self.last_index_as_trytes
    )

  @property
  def legacy_tag(self):
    # type: () -> Tag
    """
    Return the legacy tag of the transaction.
    If no legacy tag was set, returns the tag instead.
    """
    return self._legacy_tag or self.tag


class Bundle(JsonSerializable, Sequence[Transaction]):
  """
  A collection of transactions, treated as an atomic unit when
  attached to the Tangle.

  Note: unlike a block in a blockchain, bundles are not first-class
  citizens in IOTA; only transactions get stored in the Tangle.

  Instead, Bundles must be inferred by following linked transactions
  with the same bundle hash.

  References:
    - :py:class:`iota.commands.extended.get_bundles.GetBundlesCommand`
  """
  @classmethod
  def from_tryte_strings(cls, trytes):
    # type: (Iterable[TryteString]) -> Bundle
    """
    Creates a Bundle object from a list of tryte values.
    """
    return cls(map(Transaction.from_tryte_string, trytes))

  def __init__(self, transactions=None):
    # type: (Optional[Iterable[Transaction]]) -> None
    super(Bundle, self).__init__()

    self.transactions = [] # type: List[Transaction]
    if transactions:
      self.transactions.extend(
        sorted(transactions, key=attrgetter('current_index'))
      )

    self._is_confirmed = None # type: Optional[bool]
    """
    Whether this bundle has been confirmed by neighbor nodes.
    Must be set manually.

    References:
      - :py:class:`iota.commands.extended.get_transfers.GetTransfersCommand`
    """

  def __contains__(self, transaction):
    # type: (Transaction) -> bool
    return transaction in self.transactions

  def __getitem__(self, index):
    # type: (int) -> Transaction
    return self.transactions[index]

  def __iter__(self):
    # type: () -> Iterator[Transaction]
    return iter(self.transactions)

  def __len__(self):
    # type: () -> int
    return len(self.transactions)

  @property
  def is_confirmed(self):
    # type: () -> Optional[bool]
    """
    Returns whether this bundle has been confirmed by neighbor nodes.

    This attribute must be set manually.

    References:
      - :py:class:`iota.commands.extended.get_transfers.GetTransfersCommand`
    """
    return self._is_confirmed

  @is_confirmed.setter
  def is_confirmed(self, new_is_confirmed):
    # type: (bool) -> None
    """
    Sets the ``is_confirmed`` for the bundle.
    """
    self._is_confirmed = new_is_confirmed

    for txn in self:
      txn.is_confirmed = new_is_confirmed

  @property
  def hash(self):
    # type: () -> Optional[BundleHash]
    """
    Returns the hash of the bundle.

    This value is determined by inspecting the bundle's tail
    transaction, so in a few edge cases, it may be incorrect.

    If the bundle has no transactions, this method returns `None`.
    """
    try:
      return self.tail_transaction.bundle_hash
    except IndexError:
      return None

  @property
  def tail_transaction(self):
    # type: () -> Transaction
    """
    Returns the tail transaction of the bundle.
    """
    return self[0]

  def get_messages(self, errors='drop'):
    # type: (Text) -> List[Text]
    """
    Attempts to decipher encoded messages from the transactions in the
    bundle.

    :param errors:
      How to handle trytes that can't be converted, or bytes that can't
      be decoded using UTF-8:
        - 'drop':     drop the trytes from the result.
        - 'strict':   raise an exception.
        - 'replace':  replace with a placeholder character.
        - 'ignore':   omit the invalid tryte/byte sequence.
    """
    decode_errors = 'strict' if errors == 'drop' else errors

    messages = []

    for group in self.group_transactions():
      # Ignore inputs.
      if group[0].value < 0:
        continue

      message_trytes = TryteString(b'')
      for txn in group:
        message_trytes += txn.signature_message_fragment

      if message_trytes:
        try:
          messages.append(message_trytes.decode(decode_errors))
        except (TrytesDecodeError, UnicodeDecodeError):
          if errors != 'drop':
            raise

    return messages

  def as_tryte_strings(self, head_to_tail=False):
    # type: (bool) -> List[TransactionTrytes]
    """
    Returns TryteString representations of the transactions in this
    bundle.

    :param head_to_tail:
      Determines the order of the transactions:

      - ``True``: head txn first, tail txn last.
      - ``False`` (default): tail txn first, head txn last.

      Note that the order is reversed by default, as this is the way
      bundles are typically broadcast to the Tangle.
    """
    transactions = self if head_to_tail else reversed(self)
    return [t.as_tryte_string() for t in transactions]

  def as_json_compatible(self):
    # type: () -> List[dict]
    """
    Returns a JSON-compatible representation of the object.

    References:
      - :py:class:`iota.json.JsonEncoder`.
    """
    return [txn.as_json_compatible() for txn in self]

  def group_transactions(self):
    # type: () -> List[List[Transaction]]
    """
    Groups transactions in the bundle by address.
    """
    groups = []

    if self:
      last_txn = self.tail_transaction
      current_group = [last_txn]
      for current_txn in self.transactions[1:]:
        # Transactions are grouped by address, so as long as the
        # address stays consistent from one transaction to another, we
        # are still in the same group.
        if current_txn.address == last_txn.address:
          current_group.append(current_txn)
        else:
          groups.append(current_group)
          current_group = [current_txn]

        last_txn = current_txn

      if current_group:
        groups.append(current_group)

    return groups


