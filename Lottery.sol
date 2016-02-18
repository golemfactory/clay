contract Lottery {
    uint constant public maturity = 10; // blocks

    address public owner;
    uint public ownerDeposit; // golem account for commissions

    function Lottery() {
        owner = msg.sender;
    }

    function payout() {
        if (msg.sender == owner) {
            if (msg.sender.send(ownerDeposit))
                ownerDeposit = 0;
        }
    }

    // in real-life this struct can fill 2 storage words
    struct LotteryData {
        uint value;
        uint maturity;
        uint32 randVal;
        address payer;
    }

    struct WinnerProof {
        uint256 uid; // lottery id
        address winner; // winner’s address
        uint32 rangeStart; // beginning of the range
        uint32 rangeLength; // length of the range
        bytes32[] values; // values w1, . . . , wd
    }

    mapping (bytes32 => LotteryData) lotteries;

    function init(bytes32 lotteryHash) external {
        var lottery = lotteries[lotteryHash];
        if (lottery.value != 0)
            return;  // TODO: Here the sender looses his money. What should we do with it?

        // TODO: What if value is 0?
        uint payerDeposit = calculateInitialPayerDeposit(msg.value);
        lottery.value = msg.value - payerDeposit;
        lottery.maturity = block.number + maturity;
        lottery.payer = msg.sender;
    }

    function getValue(bytes32 lotteryHash) external constant returns (uint) {
        return lotteries[lotteryHash].value;
    }

    function getMaturity(bytes32 lotteryHash) external constant returns (uint) {
        return lotteries[lotteryHash].maturity;
    }

    function getRandomValue(bytes32 lotteryHash) external constant returns (uint32) {
        return lotteries[lotteryHash].randVal;
    }

    function check(bytes32 lotteryHash, uint256 uid, address winner, uint32 rangeStart,
            uint32 rangeLength, bytes32[] values) external {
        var proof = WinnerProof(uid, winner, rangeStart, rangeLength, values);
        var lottery = lotteries[lotteryHash];
        if (lottery.value == 0 || block.number <= lottery.maturity)
            return;
        if (lottery.randVal == 0) // OPT: This check might not be needed
            randomize(lotteryHash);
        if (!validateProof(lottery.randVal, lotteryHash, proof))
            return;

        winner.send(lottery.value); // FIXME: this can fail
        delete lotteries[lotteryHash];
    }

    function randomize(bytes32 lotteryHash) {
        var lottery = lotteries[lotteryHash];
        if (lottery.value == 0)
            return;
        if (lottery.randVal != 0)
            return;
        if (block.number <= lottery.maturity)
            return;

        var randomizerReward = calculatePayerDeposit(lottery.value);
        if (block.number <= lottery.maturity + 128)
            lottery.payer.send(randomizerReward); // FIXME: this can fail
        else if (block.number <= lottery.maturity + 256)
            msg.sender.send(randomizerReward); // FIXME: this can fail
        else
            ownerDeposit += randomizerReward;
        lottery.randVal = random(lottery.maturity);
        lottery.maturity = 0;
        lottery.payer = 0;
    }

    function validateProof(uint32 rand, bytes32 lotteryHash, WinnerProof proof) internal returns (bool) {
        // Check if random val falls into the range
        if (rand < proof.rangeStart || rand > proof.rangeStart + proof.rangeLength - 1) // FIXME: Check overflows, length == 0
            return false;
        // Initially, h is the value stored in the leaf (hd)
        bytes32 h = sha3(proof.winner, proof.rangeStart, proof.rangeLength);
        // Update h with hashes hd−1, ... , h0
        for (uint i = 0; i < proof.values.length; ++i)
            h = sha3(h ^ proof.values[i]);
        // Mix with uid
        h = sha3(proof.uid, h);
        return h == lotteryHash;
    }

    function changeMaturity(uint maturity) internal constant returns(uint) {
        uint begMod = (block.number - 256) % 256;
        uint matMod = maturity % 256;
        maturity = (block.number - 256) + matMod - begMod;
        if (begMod > matMod)
            maturity += 256;
        return maturity;
    }

    function random(uint maturity) internal constant returns(uint32) {
        if (block.number - maturity > 256)
            maturity = changeMaturity(maturity);
        return uint32(block.blockhash(maturity));
    }

    function calculateInitialPayerDeposit(uint val) internal constant returns (uint) {
        return val / 11;
    }
    function calculatePayerDeposit(uint val) internal constant returns (uint) {
        return val / 10;
    }
}
