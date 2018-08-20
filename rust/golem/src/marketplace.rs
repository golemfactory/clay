pub fn pick_provider(offers: &[f64]) -> u32 {
    let mut best = 0;
    for (ind, offer) in offers.iter().enumerate() {
        if offer < &offers[best] {
            best = ind;
        }
    }
    best as u32
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pick_provider_sanity() {
        assert_eq!(pick_provider(&vec![2.0, 2.2, 1.7, 4.4]), 2);
    }
}
