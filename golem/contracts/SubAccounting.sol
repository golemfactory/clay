contract SubAccounting {
    mapping(address => uint) _balance;

    event Transfer(address indexed from, address indexed to, uint256 value);

    function balanceOf(address addr) constant external returns (uint) {
        return _balance[addr];
    }

    // This function is redundant, but might make some clients simplier.
    function balance() constant external returns (uint) {
        return _balance[msg.sender];
    }

    function deposit() external {
        // TODO: Use it as an anonymous method?
        _balance[msg.sender] += msg.value;
    }

    function withdrawAll() external {
        // TODO: Should we explicitly forbid full payout?
        msg.sender.send(_balance[msg.sender]);
        _balance[msg.sender] = 0;
    }

    function withdraw(uint value) external {
        uint balance = _balance[msg.sender];
        if (balance >= value) {
            // FIXME: send() can fail if sending to another contract.
            msg.sender.send(value);
            _balance[msg.sender] -= value;
        }
    }

    function transferExt(uint[] payments) external {
        uint value = msg.value;

        for (uint i = 0; i < payments.length; ++i) {
            uint payment = payments[i];
            address addr = address(payment);
            uint v = payment / 2**160;
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

    // This function allows batch payments using sent value and sender balance
    function transfer(bytes32[] payments) external {
        uint balance = _balance[msg.sender];
        uint value = msg.value + balance; // Unlikely to overflow

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

        if (value != balance) {
            _balance[msg.sender] = value;
        }
    }
}
