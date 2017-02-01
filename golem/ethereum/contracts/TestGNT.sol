pragma solidity ^0.4.4;

contract TestGNT {
    string public constant name = "Test Golem Network Token";
    string public constant symbol = "tGNT";
    uint8 public constant decimals = 18;  // 18 decimal places, the same as ETH.
    uint256 public totalSupply;

    mapping (address => uint256) balances;

    event Transfer(address indexed _from, address indexed _to, uint256 _value);

    function transfer(address _to, uint256 _value) returns (bool) {
        var senderBalance = balances[msg.sender];
        if (senderBalance >= _value && _value > 0) {
            senderBalance -= _value;
            balances[msg.sender] = senderBalance;
            balances[_to] += _value;
            Transfer(msg.sender, _to, _value);
            return true;
        }
        return false;
    }

    // This function allows batch payments using sent value and
    // sender's balance.
    // Cost: 21000 + (5000 + ~2000) * n
    function batchTransfer(bytes32[] payments) external {
        uint balance = balances[msg.sender];

        for (uint i = 0; i < payments.length; ++i) {
            // A payment contains compressed data:
            // first 96 bits (12 bytes) is a value,
            // following 160 bits (20 bytes) is an address.
            bytes32 payment = payments[i];
            address addr = address(payment);
            uint v = uint(payment) / 2**160;
            if (v > balance) throw;
            balances[addr] += v;
            balance -= v;
            Transfer(msg.sender, addr, v);
        }

        balances[msg.sender] = balance;
    }

    function balanceOf(address _owner) external constant returns (uint256) {
        return balances[_owner];
    }

    function create() external {
        var tokens = 1000 * 10 ** uint256(decimals);
        if (balances[msg.sender] >= tokens) throw;
        balances[msg.sender] += tokens;
        totalSupply += tokens;
        Transfer(0, msg.sender, tokens);
    }
}
