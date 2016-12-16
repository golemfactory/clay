// Bank Of Deposit
//
// This contract keeps user's ethers in its internal storage. This approach
// allows cheaper batch transfers than series of individual Ethereum
// transactions.
contract BankOfDeposit {
    // OPT: solidity additionally hashes the key of the map what in case of
    //      address is a waste of gas
    mapping(address => uint) _balance;

    // This event is supposed to be identical with the one used in Coin/Token
    // interface.
    event Transfer(address indexed from, address indexed to, uint256 value);

    // Check balance of an account.
    function balanceOf(address addr) constant external returns (uint) {
        return _balance[addr];
    }

    // This function is redundant, but might make some clients simplier.
    function balance() constant external returns (uint) {
        return _balance[msg.sender];
    }

    // Deposit ethers to sender's account.
    function deposit() external {
        _balance[msg.sender] += msg.value;
    }

    // Fallback function, the same as deposit().
    function() external {
        _balance[msg.sender] += msg.value;
    }

    // Withdraw ether from bank.
    // Param `to` is the Ethereum address where the ether will be send to.
    // If not provided, message sender's address will be used.
    function withdraw(uint value, address to) external {
        // Precondition: check sender's balance is enough.
        if (_balance[msg.sender] < value)
            throw;

        // Handle default value of `to` address.
        address target = (to != 0) ? to : msg.sender;

        _balance[msg.sender] -= value;

        // Try sending ether.
        if (!target.send(value))
            throw;  // In case of failure revert the transaction.
    }

    // This function allows batch payments using sent value and
    // sender's balance.
    // Cost: 21000 + (5000 + ~2000) * n
    function transfer(bytes32[] payments) external {
        uint balance = _balance[msg.sender];
        uint value = msg.value + balance; // Unlikely to overflow

        for (uint i = 0; i < payments.length; ++i) {
            // A payment contains compressed data:
            // first 96 bits (12 bytes) is a value,
            // following 160 bits (20 bytes) is an address.
            bytes32 payment = payments[i];
            address addr = address(payment);
            uint v = uint(payment) / 2**160;
            if (v > value)
                break;
            _balance[addr] += v;
            value -= v;
            Transfer(msg.sender, addr, v);
        }

        if (value != balance) {
            // Keep the rest in sender's account.
            // OPT: Looks like solidity tries to optimize storage modification
            //      as well, so it makes it worse.
            _balance[msg.sender] = value;
        }
    }

    // This function is only for cost comparison with transfer() function.
    // The gain seems not to be greater than 1% so it should not be kept
    // in final version
    function transferExternalValue(bytes32[] payments) external {
        uint value = msg.value;

        for (uint i = 0; i < payments.length; ++i) {
            bytes32 payment = payments[i];
            address addr = address(payment);
            uint v = uint(payment) / 2**160;
            if (v > value)
                break;
            _balance[addr] += v;
            value -= v;
            Transfer(msg.sender, addr, v);
        }

        // Send left value to sender account (conditional to safe storage
        // modification costs).
        if (value > 0)
            _balance[msg.sender] += value;
    }
}
